# SWEET Watermark 改良方案實作指南

## 專案概述

### 研究目標

基於 SWEET watermark 系統，探討不同 seeding scheme 對程式碼浮水印效能的影響。

### 實驗設定

- **Model**: bigcode/starcoderbase-7b
- **Task**: HumanEval (164 problems)
- **參數**: gamma=0.25, delta=3.0, entropy_threshold=1.2
- **評估指標**:
  - AUROC: 整體區分能力
  - TPR@0%: 零誤報率下的真陽性率（最嚴格）
  - TPR@1%: 1% 誤報率下的真陽性率
  - TPR@5%: 5% 誤報率下的真陽性率（較寬鬆）

---

## 新增方法的標準流程

### 步驟 1: 理論設計

確定方法的核心概念：
- 如何從 context tokens 生成 seed
- 需要多長的 context window (k)
- 與 SWEET framework 的兼容性

### 步驟 2: 程式碼修改

需要修改 5 個位置：

1. **main.py**: 在 `--seeding_scheme` 的 choices 中加入新方法名稱
2. **watermark.py (_seed_rng)**: 實作 seed 生成邏輯
3. **watermark.py (WatermarkDetector.__init__)**: 設定 `min_prefix_len`
4. **generation.py**: 傳遞 seeding_scheme 參數
5. **evaluator.py**: 傳遞 seeding_scheme 參數

### 步驟 3: 創建執行腳本

每個方法需要 3 個 shell scripts：

```
scripts/main/{method}_run_sweet_generation.sh        # 生成帶浮水印的程式碼
scripts/main/{method}_run_sweet_detection.sh         # 檢測機器生成的程式碼
scripts/main/{method}_run_sweet_detection_human.sh   # 測試人類程式碼的誤報率
```

腳本主要參數：
- `--outputs_dir OUTPUT_{METHOD}`: 輸出目錄
- `--seeding_scheme {method}`: 指定方法

### 步驟 4: 執行實驗

完整流程（約 2-3 小時）：

```bash
bash scripts/main/{method}_run_sweet_generation.sh && \
bash scripts/main/{method}_run_sweet_detection.sh && \
bash scripts/main/{method}_run_sweet_detection_human.sh && \
python calculate_auroc_tpr.py \
    --task humaneval \
    --human_fname OUTPUT_{METHOD}_HUMAN/evaluation_results.json \
    --machine_fname OUTPUT_{METHOD}/evaluation_results.json
```

---

## 各方法實作與結果

### Method 1: Simple_1 (Baseline)

#### 論文依據

Kirchenbauer et al., "A Watermark for Large Language Models" (NeurIPS 2023)

#### 核心概念

使用單一前置 token 生成 seed：
- Context window: k=1
- Seed = hash(previous_token) × hash_key
- 最簡單的 baseline 方法

#### 執行方式

**Scripts 命名:**
- `run_sweet_generation.sh`
- `run_sweet_detection.sh`
- `run_sweet_detection_human.sh`

**輸出目錄:** `OUTPUT_DIRECTORY`

**執行指令:**
```bash
bash scripts/main/run_sweet_generation.sh && \
bash scripts/main/run_sweet_detection.sh && \
bash scripts/main/run_sweet_detection_human.sh && \
python calculate_auroc_tpr.py \
    --task humaneval \
    --human_fname OUTPUT_DIRECTORY_HUMAN/evaluation_results.json \
    --machine_fname OUTPUT_DIRECTORY/evaluation_results.json
```

#### 實驗結果

```
AUROC: 0.9242
TPR@0%: 0.5671
TPR@1%: 0.6402
TPR@5%: 0.7012
```

#### 結果分析

作為 baseline 表現尚可，AUROC 超過 0.92。優點是實作最簡單、計算最快，TPR@0% 達到 0.567 在嚴格檢測下表現相對較好。缺點是只依賴單一 token，容易被攻擊，修改任何一個 token 都會完全改變後續的 green list。

根據 Zhao et al. (2024)，k=1 方法的理論衰減係數為 2.125，在受到編輯攻擊時 z-score 降幅較大。適合快速原型開發和不需要高度抵抗攻擊的應用。

---

### Method 2: Multi-token (k=3)

#### 論文依據

Zhao et al., "Provable Robust Watermarking for AI-Generated Text" (ICLR 2024)

#### 核心概念

使用 rolling hash 結合最後 3 個 tokens：
- Context window: k=3
- 使用 prime multiplier (31) 確保良好的 hash 分布
- 每個 token 都對最終 seed 有貢獻

#### 執行方式

**Scripts 命名:**
- `multitoken_run_sweet_generation.sh`
- `multitoken_run_sweet_detection.sh`
- `multitoken_run_sweet_detection_human.sh`

**輸出目錄:** `OUTPUT_MULTITOKEN`

#### 實驗結果

```
AUROC: 0.9516
TPR@0%: 0.4939
TPR@1%: 0.4939
TPR@5%: 0.7622
```

#### 結果分析

AUROC 顯著提升到 0.952，在 k-gram 方法中表現最佳。相比 Simple_1，AUROC 提升 2.8%，但 TPR@0% 下降到 0.494，TPR@5% 提升到 0.762。

有趣的發現是 TPR@0% 和 TPR@1% 完全相同，說明檢測 threshold 有明確的"階梯效應"。優勢是對單一 token 修改更魯棒，需要連續改動 3 個 token 才能破壞浮水印。劣勢是 3-token dependency 增加了邊界情況複雜度，在嚴格 threshold 下容易誤判。

雖然理論衰減係數與 k=1 相同（2.125），但因為需要連續修改多個 token，有效編輯次數降低，整體魯棒性提升。適合需要平衡 detection accuracy 和 robustness 的場景。

---

### Method 3: Unigram

#### 論文依據

Zhao et al., "Provable Robust Watermarking for AI-Generated Text" (ICLR 2024)

#### 核心概念

完全不依賴 context，使用固定的 global green list：
- Context window: k=0
- Seed = hash_key（固定值）
- 所有位置使用相同的 green list

#### 執行方式

**Scripts 命名:**
- `unigram_run_sweet_generation.sh`
- `unigram_run_sweet_detection.sh`
- `unigram_run_sweet_detection_human.sh`

**輸出目錄:** `OUTPUT_UNIGRAM`

#### 實驗結果

```
AUROC: 0.9789
TPR@0%: 0.7195
TPR@1%: 0.7256
TPR@5%: 0.9146
```

#### 結果分析

所有指標都是最佳，AUROC 接近 0.98，是明確的贏家。AUROC 比 Multi-token 高 2.7%，TPR@0% 高達 0.720，TPR@5% 超過 0.91。

理論上 unigram 應該因為沒有利用 context 資訊而表現較差，但實驗結果完全相反。可能原因包括：(1) 固定 green list 讓每個 token 決策獨立，減少累積誤差，variance 估計更準確；(2) SWEET 只在高 entropy 位置加浮水印，固定 green list 不會過度限制語義表達；(3) 程式碼生成中很多 token 選擇是獨立的，不需要複雜的 context dependency；(4) 沒有邊界情況複雜度，檢測更穩定。

理論衰減係數只有 1.125，遠低於 k-gram 的 2.125，在相同攻擊下 z-score 下降幅度只有 k-gram 的 53%。計算最快，不需要 hash context。潛在風險是如果 hash_key 洩漏，攻擊者可以完全避開 green list。

Zhao et al. 的論文主要分析 attack robustness，但我們的實驗是 normal detection。在 normal 情況下，unigram 的簡單性反而成為優勢。適合追求最高 detection accuracy 和需要最快推理速度的場景。

---

### Method 4: CodeBERT

#### 論文依據

Feng et al., "CodeBERT: A Pre-Trained Model for Programming and Natural Languages" (EMNLP 2020)

#### 核心概念

使用語義 embedding 來生成 seed：
- Context window: k=10 tokens
- 將 context 透過 CodeBERT 編碼成 768 維 embedding
- 對 embedding 進行 hash 得到 seed

#### 執行方式

**Scripts 命名:**
- `codebert_run_sweet_generation.sh`
- `codebert_run_sweet_detection.sh`
- `codebert_run_sweet_detection_human.sh`

**輸出目錄:** `OUTPUT_CODEBERT`

#### 實驗結果

```
AUROC: 0.4880
TPR@0%: 0.0000
TPR@1%: 0.0122
TPR@5%: 0.0549
```

#### 結果分析

完全失敗。AUROC = 0.488 < 0.5（比隨機猜測還差），TPR@0% = 0（完全無法檢測），所有指標都遠低於其他方法。

失敗的根本原因是浮點數數值不穩定。核心假設是 generation 和 detection 時相同 context 應該產生相同 embedding 和 seed，但實際上：(1) GPU 浮點運算有微小誤差，即使 embedding 只差 1e-8，經過 hash 後 seed 也會完全不同；(2) Hash function 的 avalanche effect 使輸入微小變化導致輸出巨大變化；(3) GPU vs CPU 的浮點運算結果有差異；(4) StarCoder 和 CodeBERT 的 tokenizer 雙重轉換導致資訊損失；(5) Mean pooling 累積誤差。

AUROC < 0.5 表示模型在"反向"檢測浮水印。Generation 時的 seed_A 產生 green_list_A，但 Detection 時因浮點誤差產生不同的 seed_B 和 green_list_B，導致 z-score 偏低，形成負相關。

可能的解決方案包括量化 embedding、只用 [CLS] token、減少 context size、嚴格控制計算環境等，但都未實作。執行時間比其他方法慢 20-50%。

這個失敗是技術實作問題而非理論問題。學術價值在於說明語義方法在 watermarking 中的實作挑戰，提醒研究者注意浮點數精度對 hash-based 方法的影響。考慮到 unigram 已達到 0.979 的 AUROC，建議將此作為負面案例保留在論文中。目前不適用於任何場景。

---

### Method 5: Multitoken5 (k=5)

#### 論文依據

Zhao et al., "Provable Robust Watermarking for AI-Generated Text" (ICLR 2024)

#### 核心概念

Multi-token 的擴展版本：
- Context window: k=5
- Rolling hash 結合最後 5 個 tokens
- 理論上應該更難攻擊

#### 執行方式

**Scripts 命名:**
- `multitoken5_run_sweet_generation.sh`
- `multitoken5_run_sweet_detection.sh`
- `multitoken5_run_sweet_detection_human.sh`

**輸出目錄:** `OUTPUT_MULTITOKEN5`

#### 實驗結果

```
AUROC: 0.9347
TPR@0%: 0.2927
TPR@1%: 0.6463
TPR@5%: 0.8232
```

#### 結果分析

表現介於 Simple_1 和 Multi-token 之間，展現有趣的 trade-off。AUROC (0.935) 反而低於 k=3 (0.952)，不符合「k 越大越好」的直覺。TPR@0% 只有 0.293 是所有方法中最低，但 TPR@1% (0.646) 比 k=3 提升 31%，TPR@5% (0.823) 比 k=3 提升 8%。

Context Length 的 Trade-off：正面效應是更長的 context 使攻擊者需要修改更多 tokens，對局部編輯更魯棒，解釋了 TPR@5% 的優異表現。負面效應是每個位置的 green list 強烈依賴前 5 個 tokens，prefix 微小變化導致完全不同的 green list，增加邊界情況複雜度，解釋了 TPR@0% 的顯著下降。

TPR 模式（0.293 → 0.646 → 0.823）說明 k=5 的 z-score 分布有較大 variance，大量真正的 watermark samples 落在臨界區域，在 FPR=0% 時被錯過但在 FPR=1% 時被捕捉。相比之下，k=3 的 TPR@0% = TPR@1%，z-score 分布較為"二元化"。

雖然 k=3 和 k=5 的理論衰減係數相同（2.125），但更大的 k 需要更多有效編輯才能破壞 watermark，解釋了在 attack scenario 下 k=5 應該更魯棒。但在 normal detection 時，更大的 k 增加檢測難度，解釋了 TPR@0% 下降。

適合可容忍 1-5% false positive、面對局部編輯攻擊的場景。不適合需要零誤報或追求最高 AUROC 的場景。這個結果展示了嚴格檢測和容錯檢測之間的權衡，選擇 context window 大小應根據應用場景的誤報容忍度決定。