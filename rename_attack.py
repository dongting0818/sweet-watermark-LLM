
import argparse
import json
import os
import re
from variable_renaming import rename_variables, check_syntax
from tqdm import tqdm
from lm_eval import tasks


def fix_prefix(code: str, protected_code: str) -> str:
    """
    Fix the prefix of code to match the protected_code exactly.
    
    Find where the protected_code content ends in code (ignoring whitespace differences),
    then replace code's prefix with the exact protected_code.
    
    Args:
        code: The generated code that may have different prefix formatting
        protected_code: The original prompt/prefix that should be preserved exactly
    
    Returns:
        Fixed code with the prefix matching protected_code exactly
    """
    if not protected_code or not code:
        return code
    
    # Remove all whitespace from protected_code for comparison
    protected_no_ws = re.sub(r'\s+', '', protected_code)
    
    if not protected_no_ws:
        return code
    
    # Find where protected_code ends in code by matching non-whitespace characters
    code_pos = 0
    protected_pos = 0
    
    while protected_pos < len(protected_no_ws) and code_pos < len(code):
        # Skip whitespace in code
        while code_pos < len(code) and code[code_pos] in ' \t\n\r':
            code_pos += 1
        
        if code_pos >= len(code):
            break
        
        # Compare non-whitespace characters
        if code[code_pos] == protected_no_ws[protected_pos]:
            code_pos += 1
            protected_pos += 1
        else:
            # Mismatch - return original code
            return code
    
    # If we matched all of protected_code content
    if protected_pos == len(protected_no_ws):
        # Concatenate: exact protected_code + rest of code after matched portion
        return protected_code + code[code_pos:]
    
    return code

def apply_rename_attack(generations, strategy='sequential', seed=42, ratio=1.0,task_name='humaneval'):
    renamed_generations = []
    task = tasks.get_task(task_name)
    dataset = task.get_dataset()

    for idx, gens in tqdm(enumerate(generations), total=len(generations)):
        tmp=[]
        protected_code = task.get_prompt(dataset[idx])
        for idx2, gen in enumerate(gens):
            res=rename_variables(
                code=gen,
                strategy=strategy,
                seed=seed,
                ratio=ratio,
                protected_code=protected_code
            )
            # Fix the prefix to match the original protected_code exactly
            res = fix_prefix(res, protected_code)
            tmp.append(res)
        renamed_generations.append(tmp)
    return renamed_generations


def generate_output_path(input_path: str, strategy: str, ratio: float) -> str:
    """
    Generate output path based on input path, strategy and ratio.
    
    Example:
        input: generations.json, strategy=sequential, ratio=0.5
        output: generations_renamed_sequential_50.json
    """
    base, ext = os.path.splitext(input_path)
    ratio_str = f"{int(ratio * 100)}"
    return f"{base}_renamed_{strategy}_{ratio_str}{ext}"


def parse_args():
    parser = argparse.ArgumentParser(description='Apply variable renaming attack to code generations')
    parser.add_argument('--input', '-i', type=str,  default="/nfs/home/ksp0108/workplace/sweet-watermark-LLM/OUTPUT_DIRECTORY/generations.json",
                        help='Input JSON file path containing generations')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON file path (auto-generated if not specified)')
    parser.add_argument('--strategy', '-s', type=str, default='random',
                        choices=['random', 'sequential', 'obfuscate'],
                        help='Renaming strategy (default: sequential)')
    parser.add_argument('--ratio', '-r', type=float, default=1.0,
                        help='Proportion of variables to rename, 0.0-1.0 (default: 1.0)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    parser.add_argument('--task_name', type=str, default='humaneval',
                        help='Task name for lm_eval (default: humaneval)')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Auto-generate output path if not specified
    output_path = args.output if args.output else generate_output_path(args.input, args.strategy, args.ratio)
    
    print(f"Input: {args.input}")
    print(f"Output: {output_path}")
    print(f"Strategy: {args.strategy}")
    print(f"Ratio: {args.ratio}")
    print(f"Seed: {args.seed}")
    print(f"Task Name: {args.task_name}")
    print("-" * 50)
    
    with open(args.input, 'r') as f:
        data = json.load(f)

    renamed_generations = apply_rename_attack(
        data, 
        strategy=args.strategy, 
        seed=args.seed, 
        ratio=args.ratio,
        task_name=args.task_name
    )

    with open(output_path, 'w') as f:
        json.dump(renamed_generations, f, indent=4)
    
    print(f"Done! Saved to {output_path}")