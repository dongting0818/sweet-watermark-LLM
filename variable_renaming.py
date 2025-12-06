"""
Variable Renaming Attack for Watermark Detection Evaluation

This module implements a variable renaming attack to test the robustness
of watermark detection in code generation. It renames variables in Python
code while preserving the code's functionality.
"""

import ast
import random
import string
import re
from typing import Optional, Set, Dict


class VariableRenamer(ast.NodeTransformer):
    """
    AST NodeTransformer that renames all user-defined variables in Python code.
    Preserves built-in names and imported module names.
    """
    
    # Python built-in names that should not be renamed
    BUILTINS = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
    BUILTINS.update({
        'True', 'False', 'None', 'self', 'cls',
        'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict', 'set', 'tuple',
        'open', 'file', 'input', 'output', 'map', 'filter', 'zip', 'enumerate',
        'sum', 'min', 'max', 'abs', 'round', 'sorted', 'reversed',
        'isinstance', 'issubclass', 'hasattr', 'getattr', 'setattr', 'delattr',
        'type', 'object', 'super', 'property', 'classmethod', 'staticmethod',
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
        'RuntimeError', 'StopIteration', 'AssertionError', 'AttributeError',
        '__name__', '__main__', '__init__', '__call__', '__str__', '__repr__',
        '__len__', '__iter__', '__next__', '__getitem__', '__setitem__',
    })
    
    def __init__(self, rename_strategy: str = 'random', ratio: float = 1.0, protected_code: Optional[str] = None):
        """
        Initialize the VariableRenamer.
        
        Args:
            rename_strategy: Strategy for renaming variables
                - 'random': Random lowercase letters
                - 'sequential': Sequential names like v1, v2, v3
                - 'obfuscate': More aggressive obfuscation with underscores
            ratio: Proportion of variables to rename (0.0 to 1.0)
                - 1.0: Rename all variables (default)
                - 0.5: Rename 50% of variables
                - 0.0: Rename no variables
            protected_code: Code string containing variable names that should be protected from renaming
        """
        super().__init__()
        self.rename_strategy = rename_strategy
        self.ratio = max(0.0, min(1.0, ratio))  # Clamp between 0 and 1
        self.name_mapping: Dict[str, str] = {}
        self.counter = 0
        self.preserved_names: Set[str] = set()
        self.function_names: Set[str] = set()
        self.class_names: Set[str] = set()
        self.import_names: Set[str] = set()
        self.variables_to_rename: Set[str] = set()  # Variables selected for renaming based on ratio
        self.all_renameable_vars: Set[str] = set()  # All variables that could be renamed
        self.protected_names: Set[str] = set()  # Names from protected_code that should not be renamed
        
        # Extract variable names from protected_code
        if protected_code:
            self._extract_protected_names(protected_code)
    
    def _extract_protected_names(self, protected_code: str) -> None:
        """Extract variable names from protected_code that should not be renamed."""
        try:
            # Try to parse the protected code as Python AST
            tree = ast.parse(protected_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    self.protected_names.add(node.id)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.protected_names.add(node.name)
                    # Also protect function arguments
                    for arg in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                        self.protected_names.add(arg.arg)
                    if node.args.vararg:
                        self.protected_names.add(node.args.vararg.arg)
                    if node.args.kwarg:
                        self.protected_names.add(node.args.kwarg.arg)
                elif isinstance(node, ast.ClassDef):
                    self.protected_names.add(node.name)
                elif isinstance(node, ast.ExceptHandler) and node.name:
                    self.protected_names.add(node.name)
        except SyntaxError:
            # If parsing fails, use regex to extract identifiers
            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
            self.protected_names.update(re.findall(pattern, protected_code))
    
    def _generate_new_name(self, original_name: str) -> str:
        """Generate a new variable name based on the strategy."""
        self.counter += 1
        
        if self.rename_strategy == 'random':
            return ''.join(random.choices(string.ascii_lowercase, k=8))
        elif self.rename_strategy == 'sequential':
            return f'var_{self.counter}'
        elif self.rename_strategy == 'obfuscate':
            return f'_{"".join(random.choices(string.ascii_lowercase, k=6))}_{self.counter}'
        else:
            b=f'var_{self.counter}'
            c=f'_{"".join(random.choices(string.ascii_lowercase, k=6))}_{self.counter}'
            return random.choice([b,c])
            
    
    def _should_rename(self, name: str) -> bool:
        """Check if a name should be renamed (considering ratio)."""
        if not self._should_rename_base(name):
            return False
        # If ratio is less than 1.0, only rename selected variables
        if self.ratio < 1.0 and name not in self.variables_to_rename:
            return False
        return True
    
    def _collect_preserved_names(self, node: ast.AST) -> None:
        """First pass: collect names that should be preserved."""
        for child in ast.walk(node):
            # Collect imported names
            if isinstance(child, ast.Import):
                for alias in child.names:
                    name = alias.asname if alias.asname else alias.name
                    self.import_names.add(name.split('.')[0])
            elif isinstance(child, ast.ImportFrom):
                for alias in child.names:
                    name = alias.asname if alias.asname else alias.name
                    self.import_names.add(name)
            # Collect function names (optional: preserve or rename)
            elif isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
                self.function_names.add(child.name)
            # Collect class names
            elif isinstance(child, ast.ClassDef):
                self.class_names.add(child.name)
    
    def _collect_all_renameable_variables(self, node: ast.AST) -> None:
        """Collect all variables that could potentially be renamed."""
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and self._should_rename_base(child.id):
                self.all_renameable_vars.add(child.id)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._should_rename_base(child.name):
                    self.all_renameable_vars.add(child.name)
                # Collect function arguments
                for arg in child.args.args + child.args.kwonlyargs + child.args.posonlyargs:
                    if self._should_rename_base(arg.arg):
                        self.all_renameable_vars.add(arg.arg)
                if child.args.vararg and self._should_rename_base(child.args.vararg.arg):
                    self.all_renameable_vars.add(child.args.vararg.arg)
                if child.args.kwarg and self._should_rename_base(child.args.kwarg.arg):
                    self.all_renameable_vars.add(child.args.kwarg.arg)
            elif isinstance(child, ast.ClassDef):
                if self._should_rename_base(child.name):
                    self.all_renameable_vars.add(child.name)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                if self._should_rename_base(child.name):
                    self.all_renameable_vars.add(child.name)
    
    def _select_variables_to_rename(self) -> None:
        """Select a subset of variables to rename based on the ratio."""
        all_vars = list(self.all_renameable_vars)
        num_to_rename = int(len(all_vars) * self.ratio)
        
        if num_to_rename >= len(all_vars):
            self.variables_to_rename = set(all_vars)
        elif num_to_rename <= 0:
            self.variables_to_rename = set()
        else:
            # Randomly select variables to rename
            self.variables_to_rename = set(random.sample(all_vars, num_to_rename))
    
    def _should_rename_base(self, name: str) -> bool:
        """Base check if a name could be renamed (ignoring ratio)."""
        if name in self.BUILTINS:
            return False
        if name in self.preserved_names:
            return False
        if name in self.import_names:
            return False
        if name in self.protected_names:
            return False
        if name.startswith('__') and name.endswith('__'):
            return False
        return True
    
    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Visit a Name node and potentially rename it."""
        if self._should_rename(node.id):
            if node.id not in self.name_mapping:
                self.name_mapping[node.id] = self._generate_new_name(node.id)
            node.id = self.name_mapping[node.id]
        return node
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Visit a function definition and rename its arguments."""
        # Rename the function itself FIRST (before processing body)
        if self._should_rename(node.name):
            if node.name not in self.name_mapping:
                self.name_mapping[node.name] = self._generate_new_name(node.name)
            node.name = self.name_mapping[node.name]
        
        # Rename function arguments and add to mapping BEFORE visiting body
        for arg in node.args.args:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle keyword-only args
        for arg in node.args.kwonlyargs:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle positional-only args (Python 3.8+)
        for arg in node.args.posonlyargs:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle *args
        if node.args.vararg and self._should_rename(node.args.vararg.arg):
            if node.args.vararg.arg not in self.name_mapping:
                self.name_mapping[node.args.vararg.arg] = self._generate_new_name(node.args.vararg.arg)
            node.args.vararg.arg = self.name_mapping[node.args.vararg.arg]
        
        # Handle **kwargs
        if node.args.kwarg and self._should_rename(node.args.kwarg.arg):
            if node.args.kwarg.arg not in self.name_mapping:
                self.name_mapping[node.args.kwarg.arg] = self._generate_new_name(node.args.kwarg.arg)
            node.args.kwarg.arg = self.name_mapping[node.args.kwarg.arg]
        
        # Now visit child nodes (function body) - arguments are already in mapping
        self.generic_visit(node)
        return node
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        """Visit an async function definition."""
        # Rename the async function itself FIRST
        if self._should_rename(node.name):
            if node.name not in self.name_mapping:
                self.name_mapping[node.name] = self._generate_new_name(node.name)
            node.name = self.name_mapping[node.name]
        
        # Rename function arguments and add to mapping BEFORE visiting body
        for arg in node.args.args:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle keyword-only args
        for arg in node.args.kwonlyargs:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle positional-only args (Python 3.8+)
        for arg in node.args.posonlyargs:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle *args
        if node.args.vararg and self._should_rename(node.args.vararg.arg):
            if node.args.vararg.arg not in self.name_mapping:
                self.name_mapping[node.args.vararg.arg] = self._generate_new_name(node.args.vararg.arg)
            node.args.vararg.arg = self.name_mapping[node.args.vararg.arg]
        
        # Handle **kwargs
        if node.args.kwarg and self._should_rename(node.args.kwarg.arg):
            if node.args.kwarg.arg not in self.name_mapping:
                self.name_mapping[node.args.kwarg.arg] = self._generate_new_name(node.args.kwarg.arg)
            node.args.kwarg.arg = self.name_mapping[node.args.kwarg.arg]
        
        # Now visit child nodes (function body)
        self.generic_visit(node)
        return node
    
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Visit a class definition and rename it."""
        # Rename the class itself
        if self._should_rename(node.name):
            if node.name not in self.name_mapping:
                self.name_mapping[node.name] = self._generate_new_name(node.name)
            node.name = self.name_mapping[node.name]
        
        # Continue visiting child nodes (methods, attributes, etc.)
        self.generic_visit(node)
        return node
    
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        """Visit exception handler and rename the exception variable."""
        if node.name and self._should_rename(node.name):
            if node.name not in self.name_mapping:
                self.name_mapping[node.name] = self._generate_new_name(node.name)
            node.name = self.name_mapping[node.name]
        self.generic_visit(node)
        return node


def rename_variables(code: str, strategy: str = 'random', seed: Optional[int] = None, ratio: float = 1.0, protected_code: Optional[str] = None) -> str:
    """
    Rename variables in Python code.
    
    Args:
        code: Python source code as a string
        strategy: Renaming strategy ('random', 'sequential', 'obfuscate')
        seed: Random seed for reproducibility
        ratio: Proportion of variables to rename (0.0 to 1.0)
            - 1.0: Rename all variables (default)
            - 0.5: Rename 50% of variables
            - 0.0: Rename no variables
        protected_code: Code string containing variable names that should be protected from renaming
    
    Returns:
        Modified code with renamed variables, or original code if parsing fails
    """
    if seed is not None:
        random.seed(seed)
    
    # If ratio is 0, return original code
    if ratio <= 0:
        return code
    
    # If protected_code is provided, we need to preserve it exactly (including comments)
    # Split the code into protected prefix and the rest, then only rename the rest
    if protected_code:
        # Find where protected_code ends in code
        suffix_code = _extract_suffix(code, protected_code)
        if suffix_code is not None and suffix_code != code:
            # Only rename variables in the suffix part
            # Use _simple_rename to preserve comments in the suffix
            renamed_suffix = _simple_rename(suffix_code, strategy, seed, ratio, protected_code)
            # Combine protected prefix with renamed suffix
            return protected_code + renamed_suffix
    
    # No protected_code or couldn't split, rename the entire code
    return _rename_code_part(code, strategy, seed, ratio, protected_code)


def _extract_suffix(code: str, protected_code: str) -> Optional[str]:
    """
    Extract the suffix of code after the protected_code ends.
    Handles whitespace differences between code and protected_code.
    
    Returns:
        The suffix part of code after protected_code, or None if matching fails
    """
    if not protected_code or not code:
        return None
    
    # Remove all whitespace from protected_code for comparison
    protected_no_ws = re.sub(r'\s+', '', protected_code)
    
    if not protected_no_ws:
        return None
    
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
            # Mismatch
            return None
    
    # If we matched all of protected_code content
    if protected_pos == len(protected_no_ws):
        return code[code_pos:]
    
    return None


def _rename_code_part(code: str, strategy: str, seed: Optional[int], ratio: float, protected_code: Optional[str]) -> str:
    """
    Rename variables in a code part using AST or fallback to regex.
    """
    try:
        # Parse the code into an AST
        tree = ast.parse(code)
        
        # Create the renamer and collect preserved names
        renamer = VariableRenamer(rename_strategy=strategy, ratio=ratio, protected_code=protected_code)
        renamer._collect_preserved_names(tree)
        
        # If ratio < 1.0, collect all renameable variables and select subset
        if ratio < 1.0:
            renamer._collect_all_renameable_variables(tree)
            renamer._select_variables_to_rename()
        
        # Apply the transformation
        new_tree = renamer.visit(tree)
        
        # Fix missing line numbers and column offsets
        ast.fix_missing_locations(new_tree)
        
        # Convert back to source code
        return ast.unparse(new_tree)
    
    except SyntaxError as e:
        # If parsing fails, try a simpler regex-based approach
        return _simple_rename(code, strategy, seed, ratio, protected_code)
    except Exception as e:
        # Return original code if any other error occurs
        print(f"Warning: Could not rename variables: {e}")
        return code


def _simple_rename(code: str, strategy: str = 'random', seed: Optional[int] = None, ratio: float = 1.0, protected_code: Optional[str] = None) -> str:
    """
    Simple regex-based variable renaming for when AST parsing fails.
    This is less accurate but more robust.
    Skips comments and strings to avoid renaming text inside them.
    
    Args:
        code: Python source code as a string
        strategy: Renaming strategy
        seed: Random seed for reproducibility
        ratio: Proportion of variables to rename (0.0 to 1.0)
        protected_code: Code string containing variable names that should be protected from renaming
    """
    if seed is not None:
        random.seed(seed)
    
    # If ratio is 0, return original code
    if ratio <= 0:
        return code
    
    # Common Python keywords and builtins to preserve
    preserved = {
        'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
        'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
        'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
        'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
        'True', 'False', 'None', 'self', 'cls',
        'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
        'set', 'tuple', 'open', 'input', 'type', 'sum', 'min', 'max',
    }
    
    # Extract protected names from protected_code
    if protected_code:
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        protected_names = set(re.findall(pattern, protected_code))
        preserved.update(protected_names)
    
    # Find regions to skip (comments and strings)
    skip_regions = []
    
    # Match strings (single, double, triple quotes) and comments
    # Triple quotes first (greedy), then single/double quotes, then comments
    string_and_comment_pattern = r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#[^\n]*)'
    
    for match in re.finditer(string_and_comment_pattern, code):
        skip_regions.append((match.start(), match.end()))
    
    def is_in_skip_region(pos: int) -> bool:
        """Check if position is inside a comment or string."""
        for start, end in skip_regions:
            if start <= pos < end:
                return True
        return False
    
    # Find all potential variable names (simple identifiers) outside skip regions
    var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
    
    def is_function_call_or_attribute(match) -> bool:
        """Check if the match is a function call or attribute access."""
        start = match.start()
        end = match.end()
        
        # Check if preceded by a dot (attribute access like A.bb)
        if start > 0 and code[start - 1] == '.':
            return True
        
        # Check if followed by '(' (function call like abs(...))
        remaining = code[end:]
        # Skip whitespace
        stripped = remaining.lstrip()
        if stripped and stripped[0] == '(':
            return True
        
        return False
    
    # First pass: collect all unique renameable variable names (excluding those in comments/strings)
    renameable_vars = set()
    for match in re.finditer(var_pattern, code):
        if not is_in_skip_region(match.start()):
            if not is_function_call_or_attribute(match):
                name = match.group(1)
                if name not in preserved:
                    renameable_vars.add(name)
    
    renameable_vars = list(renameable_vars)
    
    # Select subset based on ratio
    num_to_rename = max(min(int(len(renameable_vars) * ratio), len(renameable_vars)), 1)  # Ensure at least one variable is renamed if ratio > 0
    if num_to_rename < len(renameable_vars):
        vars_to_rename = set(random.sample(renameable_vars, num_to_rename))
    else:
        vars_to_rename = set(renameable_vars)
    
    name_mapping = {}
    counter = [0]  # Use list for mutability in nested function
    
    def get_replacement(match):
        # Skip if inside comment or string
        if is_in_skip_region(match.start()):
            return match.group(0)
        
        # Skip if it's a function call or attribute access
        if is_function_call_or_attribute(match):
            return match.group(0)
        
        name = match.group(1)
        if name in preserved:
            return name
        if name not in vars_to_rename:
            return name  # Don't rename this variable
        if name not in name_mapping:
            counter[0] += 1
            if strategy == 'random':
                name_mapping[name] = ''.join(random.choices(string.ascii_lowercase, k=8))
            elif strategy == 'sequential':
                name_mapping[name] = f'var_{counter[0]}'
            else:
                name_mapping[name] = f'v{counter[0]}'
        return name_mapping[name]
    
    return re.sub(var_pattern, get_replacement, code)


def check_syntax(code: str) -> tuple[bool, Optional[str]]:
    """
    Check if Python code has valid syntax.
    
    Args:
        code: Python source code as a string
    
    Returns:
        A tuple of (is_valid, error_message):
            - is_valid: True if syntax is valid, False otherwise
            - error_message: None if valid, error description if invalid
    """
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        error_msg = f"SyntaxError at line {e.lineno}, column {e.offset}: {e.msg}"
        return False, error_msg
    except Exception as e:
        return False, f"Error: {str(e)}"


def is_valid_python(code: str) -> bool:
    """
    Simple check if Python code has valid syntax.
    
    Args:
        code: Python source code as a string
    
    Returns:
        True if syntax is valid, False otherwise
    """
    is_valid, _ = check_syntax(code)
    return is_valid


def apply_rename_attack(generations: list, strategy: str = 'random', seed: Optional[int] = None, ratio: float = 1.0, protected_code: Optional[str] = None) -> list:
    """
    Apply variable renaming attack to a list of code generations.
    
    Args:
        generations: List of lists of generated code strings
        strategy: Renaming strategy
        seed: Random seed for reproducibility
        ratio: Proportion of variables to rename (0.0 to 1.0)
            - 1.0: Rename all variables (default)
            - 0.5: Rename 50% of variables
            - 0.0: Rename no variables
        protected_code: Code string containing variable names that should be protected from renaming
    
    Returns:
        List of lists of renamed code strings
    """
    renamed_generations = []
    
    for gen_list in generations:
        renamed_list = []
        for code in gen_list:
            renamed_code = rename_variables(code, strategy=strategy, seed=seed, ratio=ratio, protected_code=protected_code)
            renamed_list.append(renamed_code)
        renamed_generations.append(renamed_list)
    
    return renamed_generations


# Example usage and testing
if __name__ == "__main__":
    # Define protected code - variables in this code will NOT be renamed
    protected_code="import A\n"
    test_code = "import A\n# 123\napple=123\nbb=1234\ncc=1234\ndd=12345\nprint(abs( apple ))#haha\nprint(A.CC.cc( apple ))\n"
    
    print("Original code:")
    print(test_code)
    print("\n" + "="*50 + "\n")
    
    print("Protected code (variables in this code will NOT be renamed):")
    print(protected_code)
    print("\n" + "="*50 + "\n")
    
    good=0
    bad=0

    print("\n" + "="*50)
    print("Testing different ratios with protected_code:")
    print("="*50 + "\n")
    for strategy in ['random', 'sequential', 'obfuscate']:
        for ratio in [0.0, 0.25, 0.5, 0.75, 1.0]:
            print(f"Renamed code (strategy: {strategy}, ratio: {ratio}):")
            renamed = rename_variables(test_code, strategy=strategy, seed=42, ratio=ratio, protected_code=protected_code)
            print(renamed)
            vaild, error = check_syntax(renamed)
            if(not vaild):
                print(f"Syntax Error: {error}")
                bad+=1
            else:
                good+=1
            print("\n" + "-"*50 + "\n")
    print(f"Total valid codes: {good}, Total invalid codes: {bad}")
    

