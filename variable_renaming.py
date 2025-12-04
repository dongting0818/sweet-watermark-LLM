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
    
    def __init__(self, rename_strategy: str = 'random'):
        """
        Initialize the VariableRenamer.
        
        Args:
            rename_strategy: Strategy for renaming variables
                - 'random': Random lowercase letters
                - 'sequential': Sequential names like v1, v2, v3
                - 'obfuscate': More aggressive obfuscation with underscores
        """
        super().__init__()
        self.rename_strategy = rename_strategy
        self.name_mapping: Dict[str, str] = {}
        self.counter = 0
        self.preserved_names: Set[str] = set()
        self.function_names: Set[str] = set()
        self.class_names: Set[str] = set()
        self.import_names: Set[str] = set()
    
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
            return f'v{self.counter}'
    
    def _should_rename(self, name: str) -> bool:
        """Check if a name should be renamed."""
        if name in self.BUILTINS:
            return False
        if name in self.preserved_names:
            return False
        if name in self.import_names:
            return False
        if name.startswith('__') and name.endswith('__'):
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
    
    def visit_Name(self, node: ast.Name) -> ast.Name:
        """Visit a Name node and potentially rename it."""
        if self._should_rename(node.id):
            if node.id not in self.name_mapping:
                self.name_mapping[node.id] = self._generate_new_name(node.id)
            node.id = self.name_mapping[node.id]
        return node
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Visit a function definition and rename its arguments."""
        # Rename function arguments
        for arg in node.args.args:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        # Handle *args and **kwargs
        if node.args.vararg and self._should_rename(node.args.vararg.arg):
            if node.args.vararg.arg not in self.name_mapping:
                self.name_mapping[node.args.vararg.arg] = self._generate_new_name(node.args.vararg.arg)
            node.args.vararg.arg = self.name_mapping[node.args.vararg.arg]
        
        if node.args.kwarg and self._should_rename(node.args.kwarg.arg):
            if node.args.kwarg.arg not in self.name_mapping:
                self.name_mapping[node.args.kwarg.arg] = self._generate_new_name(node.args.kwarg.arg)
            node.args.kwarg.arg = self.name_mapping[node.args.kwarg.arg]
        
        # Optionally rename the function itself
        # Uncomment if you want to rename function names too
        # if self._should_rename(node.name):
        #     if node.name not in self.name_mapping:
        #         self.name_mapping[node.name] = self._generate_new_name(node.name)
        #     node.name = self.name_mapping[node.name]
        
        # Continue visiting child nodes
        self.generic_visit(node)
        return node
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        """Visit an async function definition."""
        # Same logic as FunctionDef
        for arg in node.args.args:
            if self._should_rename(arg.arg):
                if arg.arg not in self.name_mapping:
                    self.name_mapping[arg.arg] = self._generate_new_name(arg.arg)
                arg.arg = self.name_mapping[arg.arg]
        
        self.generic_visit(node)
        return node
    
    def visit_arg(self, node: ast.arg) -> ast.arg:
        """Visit function argument."""
        if self._should_rename(node.arg):
            if node.arg not in self.name_mapping:
                self.name_mapping[node.arg] = self._generate_new_name(node.arg)
            node.arg = self.name_mapping[node.arg]
        return node
    
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        """Visit exception handler and rename the exception variable."""
        if node.name and self._should_rename(node.name):
            if node.name not in self.name_mapping:
                self.name_mapping[node.name] = self._generate_new_name(node.name)
            node.name = self.name_mapping[node.name]
        self.generic_visit(node)
        return node


def rename_variables(code: str, strategy: str = 'random', seed: Optional[int] = None) -> str:
    """
    Rename variables in Python code.
    
    Args:
        code: Python source code as a string
        strategy: Renaming strategy ('random', 'sequential', 'obfuscate')
        seed: Random seed for reproducibility
    
    Returns:
        Modified code with renamed variables, or original code if parsing fails
    """
    if seed is not None:
        random.seed(seed)
    
    try:
        # Parse the code into an AST
        tree = ast.parse(code)
        
        # Create the renamer and collect preserved names
        renamer = VariableRenamer(rename_strategy=strategy)
        renamer._collect_preserved_names(tree)
        
        # Apply the transformation
        new_tree = renamer.visit(tree)
        
        # Fix missing line numbers and column offsets
        ast.fix_missing_locations(new_tree)
        
        # Convert back to source code
        return ast.unparse(new_tree)
    
    except SyntaxError as e:
        # If parsing fails, try a simpler regex-based approach
        return _simple_rename(code, strategy, seed)
    except Exception as e:
        # Return original code if any other error occurs
        print(f"Warning: Could not rename variables: {e}")
        return code


def _simple_rename(code: str, strategy: str = 'random', seed: Optional[int] = None) -> str:
    """
    Simple regex-based variable renaming for when AST parsing fails.
    This is less accurate but more robust.
    """
    if seed is not None:
        random.seed(seed)
    
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
    
    # Find all potential variable names (simple identifiers)
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
    
    name_mapping = {}
    counter = [0]  # Use list for mutability in nested function
    
    def get_replacement(match):
        name = match.group(1)
        if name in preserved:
            return name
        if name not in name_mapping:
            counter[0] += 1
            if strategy == 'random':
                name_mapping[name] = ''.join(random.choices(string.ascii_lowercase, k=8))
            elif strategy == 'sequential':
                name_mapping[name] = f'var_{counter[0]}'
            else:
                name_mapping[name] = f'v{counter[0]}'
        return name_mapping[name]
    
    return re.sub(pattern, get_replacement, code)


def apply_rename_attack(generations: list, strategy: str = 'random', seed: Optional[int] = None) -> list:
    """
    Apply variable renaming attack to a list of code generations.
    
    Args:
        generations: List of lists of generated code strings
        strategy: Renaming strategy
        seed: Random seed for reproducibility
    
    Returns:
        List of lists of renamed code strings
    """
    renamed_generations = []
    
    for gen_list in generations:
        renamed_list = []
        for code in gen_list:
            renamed_code = rename_variables(code, strategy=strategy, seed=seed)
            renamed_list.append(renamed_code)
        renamed_generations.append(renamed_list)
    
    return renamed_generations


# Example usage and testing
if __name__ == "__main__":
    test_code = '''
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total

result = calculate_sum([1, 2, 3, 4, 5])
print(result)
'''
    
    print("Original code:")
    print(test_code)
    print("\n" + "="*50 + "\n")
    
    for strategy in ['random', 'sequential', 'obfuscate']:
        print(f"Renamed code (strategy: {strategy}):")
        renamed = rename_variables(test_code, strategy=strategy, seed=42)
        print(renamed)
        print("\n" + "="*50 + "\n")
