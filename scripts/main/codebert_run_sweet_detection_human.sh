#!/bin/bash
export CUDA_VISIBLE_DEVICES=0

task="humaneval"
max_len=512
batch_size=20
top_p=0.95
n_sample=40

accelerate launch main.py \
    --model bigcode/starcoderbase-7b \
    --use_auth_token \
    --task $task \
    --temperature 0.2 \
    --precision bf16 \
    --batch_size $batch_size \
    --allow_code_execution \
    --do_sample \
    --top_p $top_p \
    --n_samples $n_sample \
    --max_length_generation $max_len \
    --detect_human_code \
    --outputs_dir OUTPUT_CODEBERT_HUMAN \
    --sweet \
    --gamma 0.25 \
    --delta 3.0 \
    --entropy_threshold 1.2 \
    --seeding_scheme codebert