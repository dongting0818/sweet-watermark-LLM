## Introduction
Official repository of the paper:
"[Who Wrote this Code? Watermarking for Code Generation](https://arxiv.org/abs/2305.15060)" 

## 模型選擇
因為使用SWEET官方github repo裡寫的bigcode/starcoder會CUDA OOM，所以改用bigcode/starcoderbase-7b，最後AUROC不會差很多。（如果你有H100 access也可以用 bigcode/starcoder）

## 最重要的指標
我認為是AUROC，因為它衡量模型在所有 threshold 下的整體區分能力，能直接反映 AI 生成與人類撰寫內容的可分性。而且還比 TPR / FPR 更穩定、不受類別不平衡或參數調整影響，是最能代表水印是否真正有效的指標。

## Reproducing the Main Experiments

### 1. 設置環境
用requirement.txt或environment.yml都可
### 2. 生成模型輸出
```
bash scripts/main/run_sweet_generation.sh
```
運行後會輸出：
OUTPUT_DIRECTORY/generations.json
### 3. 生成人工 baseline（Human Generation Baseline）
```
bash scripts/main/run_sweet_detection_human.sh
```
運行後會輸出：
OUTPUT_DIRECTORY_HUMAN/evaluation_results.json
### 3. Watermark Detection
針對 machine generations：
```
bash scripts/main/run_sweet_detection.sh
```
運行後會輸出：
OUTPUT_DIRECTORY/evaluation_results.json
### 4. 計算 AUROC / TPR
```
python calculate_auroc_tpr.py \
    --task humaneval \
    --human_fname   OUTPUT_DIRECTORY_HUMAN/evaluation_results.json \
    --machine_fname OUTPUT_DIRECTORY/evaluation_results.json
```
### 5. 結果
```
0.8280599345627602 
0.3048780487804878 
0.3231707317073171 
0.5
```
* 如果照著github的gamma、delta、entropy threshold => 0.608
* 改成現在這個版本 => 0.828
* 數字意義（按照順序）：AUROC、TPR1、TPR2、TPR3

---

## Variable Renaming Attack

用於測試水印檢測的魯棒性，通過重命名程式碼中的變數名稱來攻擊水印。

### 使用方式

```bash
# 基本用法
python rename_attack.py -i generations.json

# 指定參數
python rename_attack.py -i generations.json -s sequential -r 0.5

# 完整參數範例
python rename_attack.py --input ./OUTPUT_DIRECTORY/generations.json --strategy random --ratio 0.75 --seed 123
```

### 參數說明

| 參數 | 簡寫 | 說明 | 預設值 |
|------|------|------|--------|
| `--input` | `-i` | 輸入 JSON 檔案路徑 | (必須) |
| `--output` | `-o` | 輸出 JSON 檔案路徑 | 自動生成 |
| `--strategy` | `-s` | 重命名策略 (`random`, `sequential`, `obfuscate`) | `sequential` |
| `--ratio` | `-r` | 重命名比例 (0.0-1.0) | `1.0` |
| `--seed` | | 隨機種子 | `42` |

### 重命名策略

- **`random`**: 隨機生成 8 個小寫字母作為變數名
- **`sequential`**: 使用 `var_1`, `var_2`, ... 依序命名
- **`obfuscate`**: 使用 `_xxxx_1` 格式的混淆命名

### 自動輸出路徑

當不指定 `--output` 時，會自動根據輸入檔名、策略和比例生成輸出路徑：
- `generations.json` + `sequential` + `0.5` → `generations_renamed_sequential_50.json`

### 比例參數 (ratio)

- `ratio=1.0`: 重命名所有變數（預設）
- `ratio=0.5`: 隨機選擇 50% 的變數重命名
- `ratio=0.0`: 不重命名任何變數