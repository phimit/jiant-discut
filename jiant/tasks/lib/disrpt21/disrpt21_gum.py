import numpy as np
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import List, Union
import sys

from jiant.tasks.core import (
    BaseExample,
    BaseTokenizedExample,
    BaseDataRow,
    BatchMixin,
    Task,
    TaskTypes,
)
from jiant.tasks.lib.templates.shared import (
    labels_to_bimap,
    create_input_set_from_tokens_and_segments,
    construct_single_input_tokens_and_segment_ids,
    pad_single_with_feat_spec,
)
from jiant.utils.python.datastructures import zip_equal
from jiant.utils.python.io import read_file_lines

ARBITRARY_OVERLY_LONG_WORD_CONSTRAINT = 100
# In a rare number of cases, a single word (usually something like a mis-processed URL)
#  is overly long, and should not be treated as a real multi-subword-token word.
# In these cases, we simply replace it with an UNK token.


@dataclass
class Example(BaseExample):
    guid: str
    tokens: List[str]
    label_list: List[str]

    def tokenize(self, tokenizer):
        all_tokenized_tokens = []
        labels = []
        label_mask = []
        for token, label in zip_equal(self.tokens, self.label_list):
            # Tokenize each "token" separately, assign label only to first token
            tokenized = tokenizer.tokenize(token)
            # If the token can't be tokenized, or is too long, replace with a single <unk>
            if len(tokenized) == 0 or len(tokenized) > ARBITRARY_OVERLY_LONG_WORD_CONSTRAINT:
                tokenized = [tokenizer.unk_token]
            all_tokenized_tokens += tokenized
            padding_length = len(tokenized) - 1
            labels += [Disrpt.LABEL_TO_ID.get(label, None)] + [None] * padding_length
            label_mask += [1] + [0] * padding_length

        return TokenizedExample(
            guid=self.guid,
            tokens=all_tokenized_tokens,
            labels=labels,
            label_mask=label_mask,
        )


@dataclass
class TokenizedExample(BaseTokenizedExample):
    guid: str
    tokens: List
    labels: List[Union[int, None]]
    label_mask: List[int]

    def featurize(self, tokenizer, feat_spec):
        unpadded_inputs = construct_single_input_tokens_and_segment_ids(
            input_tokens=self.tokens,
            tokenizer=tokenizer,
            feat_spec=feat_spec,
        )
        input_set = create_input_set_from_tokens_and_segments(
            unpadded_tokens=unpadded_inputs.unpadded_tokens,
            unpadded_segment_ids=unpadded_inputs.unpadded_segment_ids,
            tokenizer=tokenizer,
            feat_spec=feat_spec,
        )

        # Replicate padding / additional tokens for the label ids and mask
        if feat_spec.sep_token_extra:
            label_suffix = [None, None]
            mask_suffix = [0, 0]
            special_tokens_count = 3  # CLS, SEP-SEP
        else:
            label_suffix = [None]
            mask_suffix = [0]
            special_tokens_count = 2  # CLS, SEP
        unpadded_labels = (
            [None] + self.labels[: feat_spec.max_seq_length - special_tokens_count] + label_suffix
        )
        unpadded_labels = [i if i is not None else -1 for i in unpadded_labels]
        unpadded_label_mask = (
            [0] + self.label_mask[: feat_spec.max_seq_length - special_tokens_count] + mask_suffix
        )

        padded_labels = pad_single_with_feat_spec(
            ls=unpadded_labels,
            feat_spec=feat_spec,
            pad_idx=-1,
        )
        padded_label_mask = pad_single_with_feat_spec(
            ls=unpadded_label_mask,
            feat_spec=feat_spec,
            pad_idx=0,
        )

        return DataRow(
            guid=self.guid,
            input_ids=np.array(input_set.input_ids),
            input_mask=np.array(input_set.input_mask),
            segment_ids=np.array(input_set.segment_ids),
            label_ids=np.array(padded_labels),
            label_mask=np.array(padded_label_mask),
            tokens=unpadded_inputs.unpadded_tokens,
        )


@dataclass
class DataRow(BaseDataRow):
    guid: str
    input_ids: np.ndarray
    input_mask: np.ndarray
    segment_ids: np.ndarray
    label_ids: np.ndarray
    label_mask: np.ndarray
    tokens: list


@dataclass
class Batch(BatchMixin):
    input_ids: torch.LongTensor
    input_mask: torch.LongTensor
    segment_ids: torch.LongTensor
    label_ids: torch.LongTensor
    label_mask: torch.LongTensor
    tokens: list




class DisrptTask(Task):

    Example = Example
    TokenizedExample = Example
    DataRow = DataRow
    Batch = Batch

    TASK_TYPE = TaskTypes.TAGGING
    LABELS = ["_","BeginSeg=Yes"]
    LABEL_TO_ID, ID_TO_LABEL = labels_to_bimap(LABELS)

    RNN_MODULES = {
        "lstm": nn.LSTM,
        "gru": nn.GRU,
    }   

    # PM TODO: 
    # - we reproduce panx subtask system here by giving a corpus name 
    # this influence the reading part too
    # for now, we set the default to gum to avoid problem downstream
    # - To modify the head (just a projection, we might want to add an LSTM): add parameters in config, 
    # declare them here. When the head is created, it has access to the task -> create the model from the task config
    # it's the easiest way to propagate task config to the task head
    # - can it be done for backbone too ? unlikely but must be checked 
    def __init__(self, name, path_dict, corpus="eng.rst.gum",**kwargs):
        """default constructor argument are path_dict to train/val/test and name of task
        
        additional for segmentation (may be in kwargs): 
           - corpus origin if we want to automate training every one of them at once (not implemented); explicit argument but must be in kwargs of config
           - recurrent_layer = None/lstm/gru
           - if previous arg is not none, will use an argument "rnn_config", which contains at least a "hidden_size" argument, and 
             may have also all RNN constructor optional argument (eg bidirectional, cf torch documentation)
        """
        super().__init__(name=name, path_dict=path_dict)
        self.corpus = corpus
        ## here we should overrides TAGGING init to add a RNN if we want
        ## (not so simple ... check how TAGGING is called at TASK creation + what goes to the HEAD -> how to override the head ?)
        recurrent_layer = kwargs.get("recurrent_layer")
        if recurrent_layer != "None": 
            self.rnn_type = recurrent_layer
            self.rnn_cfg = kwargs["rnn_config"]                          
            #self.rnn = recurrent_modules[recurrent_layer](input_size=hidden_size,**kwargs["rnn_config"])
            #output_size = kwargs["rnn_config"]["hidden_size"]
            #self.projection = nn.Linear(output_size, self.num_labels)
            self.classif_type = "recurrent_layer"
        else:
            self.classif_type = "simple"
        print(self.__dict__)



    @property
    def num_labels(self):
        return len(self.LABELS)

    def get_train_examples(self):
        return self._create_examples(data_path=self.path_dict["train"], set_type="train")

    def get_val_examples(self):
        return self._create_examples(data_path=self.path_dict["val"], set_type="val")

    def get_test_examples(self):
        return self._create_examples(data_path=self.path_dict["test"], set_type="test")

    @classmethod
    def _create_examples(cls, data_path, set_type):
        """disrpt21 format has 10 fields: 
            1 = token number in sentence or text
            2 = token
            3-9 = empty "_" or syntax info (lemma/supertag/postag/... etc)
            10 has segmentation label + info for syntax/deep syntax all separated by "|"
        """
        curr_token_list, curr_label_list = [], []
        data_lines = read_file_lines(data_path, "r", encoding="utf-8")
        examples = []
        idx = 0
        for data_line in data_lines:
            data_line = data_line.strip()
            if data_line:
                if data_line.startswith("#"):
                    pass
                else:
                    _, token, *useless, labels = data_line.split("\t")
                    label_set = set(labels.split("|"))
                    # 0 = _, 1 = segment boudary
                    if cls.LABELS[1] in label_set:
                        label = cls.LABELS[1]
                    else:
                        label = cls.LABELS[0]
                    
                    curr_token_list.append(token)
                    curr_label_list.append(label)
            else:
                examples.append(
                    Example(
                        guid="%s-%s" % (set_type, idx),
                        tokens=curr_token_list,
                        label_list=curr_label_list,
                    )
                )
                idx += 1
                curr_token_list, curr_label_list = [], []
        if curr_token_list:
            examples.append(
                Example(guid="%s-%s" % (idx, idx), tokens=curr_token_list, label_list=curr_label_list)
            )
        return examples
