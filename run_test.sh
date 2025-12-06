#!/bin/bash

# Variable Renaming Attack Testing Script
# Tests watermark detection robustness against rename attacks at different levels

# Configuration
METHODS=("DIRECTORY" "MULTITOKEN" "MULTITOKEN5" "UNIGRAM" "CODEBERT")
#METHODS=("MULTITOKEN5")
RATIOS=(0.0 0.25 0.5 0.75 1.0)
STRATEGY="defualt"  # Can be: random, sequential, obfuscate

echo "=========================================="
echo "Starting Variable Renaming Attack Tests"
echo "=========================================="
echo "Methods: ${METHODS[@]}"
echo "Ratios: ${RATIOS[@]}"
echo "Strategy: $STRATEGY"
echo "=========================================="

# Loop through each method
for METHOD in "${METHODS[@]}"; do
    echo ""
    echo "=========================================="
    echo "Processing METHOD: $METHOD"
    echo "=========================================="
    
    # Set input/output paths based on method
    if [ "$METHOD" = "DIRECTORY" ]; then
        INPUT_DIR="OUTPUT_DIRECTORY"
    else
        INPUT_DIR="OUTPUT_${METHOD}"
    fi
    
    INPUT_FILE="${INPUT_DIR}/generations.json"
    
    # Check if input file exists
    if [ ! -f "$INPUT_FILE" ]; then
        echo "Warning: $INPUT_FILE not found, skipping $METHOD"
        continue
    fi
    
    # Loop through each ratio
    for RATIO in "${RATIOS[@]}"; do
        echo ""
        echo "------------------------------------------"
        echo "Testing ratio: $RATIO (${RATIO}00% renaming)"
        echo "------------------------------------------"
        
        # Convert ratio to percentage for naming
        RATIO_PCT=$(echo "$RATIO * 100" | bc | cut -d'.' -f1)
        
        OUTPUT_FILE="${INPUT_DIR}/generations_renamed_${STRATEGY}_${RATIO_PCT}.json"
        EVAL_OUTPUT_DIR="${INPUT_DIR}_RENAMED_${RATIO_PCT}"
        
        # Step 1: Perform rename attack
        echo "[1/3] Performing rename attack..."
        python rename_attack.py \
            --input "$INPUT_FILE" \
            --output "$OUTPUT_FILE" \
            --strategy "$STRATEGY" \
            --ratio "$RATIO"
        
        if [ $? -ne 0 ]; then
            echo "Error: Rename attack failed for $METHOD at ratio $RATIO"
            continue
        fi
        
        # Step 2: Run detection on renamed code
        echo "[2/3] Running watermark detection..."
        
        # Determine seeding scheme
        if [ "$METHOD" = "DIRECTORY" ]; then
            SEEDING_SCHEME="simple_1"
        elif [ "$METHOD" = "MULTITOKEN" ]; then
            SEEDING_SCHEME="multi_token"
        elif [ "$METHOD" = "MULTITOKEN5" ]; then
            SEEDING_SCHEME="multitoken5"
        elif [ "$METHOD" = "UNIGRAM" ]; then
            SEEDING_SCHEME="unigram"
        elif [ "$METHOD" = "CODEBERT" ]; then
            SEEDING_SCHEME="codebert"
        fi
        
        export CUDA_VISIBLE_DEVICES=4
        accelerate launch --num_processes=1 main.py \
            --model bigcode/starcoderbase-7b \
            --use_auth_token \
            --task humaneval \
            --temperature 0.2 \
            --precision bf16 \
            --batch_size 20 \
            --allow_code_execution \
            --do_sample \
            --top_p 0.95 \
            --n_samples 40 \
            --max_length_generation 512 \
            --load_generations_path "$OUTPUT_FILE" \
            --outputs_dir "$EVAL_OUTPUT_DIR" \
            --sweet \
            --gamma 0.25 \
            --delta 3.0 \
            --entropy_threshold 1.2 \
            --seeding_scheme "$SEEDING_SCHEME"
        
        if [ $? -ne 0 ]; then
            echo "Error: Detection failed for $METHOD at ratio $RATIO"
            continue
        fi
        
        # Step 3: Calculate AUROC and TPR
        echo "[3/3] Calculating AUROC and TPR..."
        
        # Use corresponding human baseline
        if [ "$METHOD" = "DIRECTORY" ]; then
            HUMAN_FILE="OUTPUT_DIRECTORY_HUMAN/evaluation_results.json"
        else
            HUMAN_FILE="OUTPUT_${METHOD}_HUMAN/evaluation_results.json"
        fi
        
        # Check if human baseline exists
        if [ ! -f "$HUMAN_FILE" ]; then
            echo "Warning: Human baseline $HUMAN_FILE not found, using OUTPUT_DIRECTORY_HUMAN/evaluation_results.json"
            HUMAN_FILE="OUTPUT_DIRECTORY_HUMAN/evaluation_results.json"
        fi
        
        python calculate_auroc_tpr.py \
            --task humaneval \
            --human_fname "$HUMAN_FILE" \
            --machine_fname "${EVAL_OUTPUT_DIR}/evaluation_results.json" \
            > "${EVAL_OUTPUT_DIR}/metrics.txt"
        
        if [ $? -eq 0 ]; then
            echo "Results saved to ${EVAL_OUTPUT_DIR}/metrics.txt"
            echo "--- Metrics ---"
            cat "${EVAL_OUTPUT_DIR}/metrics.txt"
            echo "---------------"
        else
            echo "Error: AUROC calculation failed for $METHOD at ratio $RATIO"
        fi
        
        echo "Completed: $METHOD at ratio $RATIO"
    done
    
    echo ""
    echo "Finished all ratios for $METHOD"
done

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
echo ""
echo "Summary of results:"
for METHOD in "${METHODS[@]}"; do
    if [ "$METHOD" = "DIRECTORY" ]; then
        INPUT_DIR="OUTPUT_DIRECTORY"
    else
        INPUT_DIR="OUTPUT_${METHOD}"
    fi
    
    echo ""
    echo "$METHOD:"
    for RATIO in "${RATIOS[@]}"; do
        RATIO_PCT=$(echo "$RATIO * 100" | bc | cut -d'.' -f1)
        METRICS_FILE="${INPUT_DIR}_RENAMED_${RATIO_PCT}/metrics.txt"
        if [ -f "$METRICS_FILE" ]; then
            echo "  ${RATIO_PCT}%: $(head -n 1 $METRICS_FILE)"
        fi
    done
done