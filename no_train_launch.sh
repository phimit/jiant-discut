# testing loading a model for test prediction only

# argument $1 is the task to train on
# argument $2 is the path to the run from another task (where the best_model will be taken from)
# argument $3 is the GPU card nb

#export SPLIT=("disrpt23_por_pdtb_crpc_split" "disrpt23_tha_pdtb_tdtb_split" "disrpt23_deu_rst_pcc_split" "disrpt23_eng_dep_scidtb_split" "disrpt23_eng_rst_gum_split" "disrpt23_eng_pdtb_pdtb_split" "disrpt23_eng_rst_rstdt_split" "disrpt23_eng_sdrt_stac_split" "disrpt23_eus_rst_ert_split" "disrpt23_fas_rst_prstc_split" "disrpt23_fra_sdrt_annodis_split" "disrpt23_ita_pdtb_luna_split" "disrpt23_nld_rst_nldt_split" "disrpt23_por_rst_cstn_split" "disrpt23_rus_rst_rrt_split" "disrpt23_spa_rst_rststb_split" "disrpt23_spa_rst_sctb_split" "disrpt23_tur_pdtb_tdb_split" "disrpt23_zho_dep_scidtb_split" "disrpt23_zho_pdtb_cdtb_split" "disrpt23_zho_rst_gcdt_split" "disrpt23_zho_rst_sctb_split")


#export CONLLU=("disrpt23_por_pdtb_crpc_conllu" "disrpt23_tha_pdtb_tdtb_conllu" "disrpt23_deu_rst_pcc_conllu" "disrpt23_eng_dep_scidtb_conllu" "disrpt23_eng_pdtb_pdtb_conllu" "disrpt23_eng_rst_gum_conllu" "disrpt23_eng_rst_rstdt_conllu" "disrpt23_eng_sdrt_stac_conllu" "disrpt23_eus_rst_ert_conllu" "disrpt23_fas_rst_prstc_conllu" "disrpt23_fra_sdrt_annodis_conllu" "disrpt23_ita_pdtb_luna_conllu" "disrpt23_nld_rst_nldt_conllu" "disrpt23_por_rst_cstn_conllu" "disrpt23_rus_rst_rrt_conllu" "disrpt23_spa_rst_rststb_conllu" "disrpt23_spa_rst_sctb_conllu" "disrpt23_tur_pdtb_tdb_conllu" "disrpt23_zho_dep_scidtb_conllu" "disrpt23_zho_pdtb_cdtb_conllu" "disrpt23_zho_rst_gcdt_conllu" "disrpt23_zho_rst_sctb_conllu")

# cant specify MT like this
#export CORPORA=("disrpt23_spa_rst_rststb_conllu" "disrpt23_spa_rst_sctb_conllu")

export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=$3


export MODEL=xlm-roberta-large
#export MODEL=bert-base-multilingual-uncased
#export MODEL=bigscience/bloom-1b1


# set parameters for XLMlarge vs XLMbase or BERT
[[ $MODEL == "xlm-roberta-large" ]] \
    && BATCH_SIZE=1 \
	|| BATCH_SIZE=16

[[ $MODEL == "xlm-roberta-large" ]] \
    && FROZEN="0-5" \
	|| FROZEN="0-2"


# forcing a model for now
export forced_model="runs/run_disrpt23_eng_rst_gum_conllu_xlm-roberta-large/1684916105/" 

#for dataset in "$1"; 
# forcing a dataset for testing
for dataset in "disrpt23_eng_rst_gum_conllu"; 
do
 #does not work for multitask setup
 #rm -rf ./cache/$dataset
 echo "training on ..." $dataset
 set -x
 python simple_mtl_run.py "${dataset}" --model-name $MODEL --epochs 10 --eval-every-step 500 \
   --batch-size $BATCH_SIZE --gradient-accumulation-steps 4 --no_improvements_for_n_evals 10 \
   --config-dir exp/tasks/configs/disrpt23 --freeze-layers $FROZEN --test --continue-with "$forced_model" --predict-only
done; 
# if we dont want to do the test / do it separately
# 1) get the result dir (last run)
# 2) bash scripts/predict_only.sh $RESULT_DIR
# 3) convert the results using decode_preds.py 
#done; 
