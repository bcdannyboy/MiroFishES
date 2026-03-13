import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_tree(relative_path: str) -> ast.AST:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    return ast.parse(source, filename=relative_path)


def _collect_cli_flags(tree: ast.AST) -> set[str]:
    flags = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            flags.add(first_arg.value)
    return flags


def _get_class_init_args(tree: ast.AST, class_name: str) -> list[str]:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                return [arg.arg for arg in child.args.args]
    raise AssertionError(f"Class not found: {class_name}")


def _has_named_call(tree: ast.AST, func_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == func_name:
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == func_name:
            return True
    return False


def _has_random_seed_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "seed":
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "random":
            return True
    return False


def _constructor_keyword_names(tree: ast.AST, class_name: str) -> set[str]:
    keyword_names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != class_name:
            continue
        for keyword in node.keywords:
            if keyword.arg:
                keyword_names.add(keyword.arg)
    return keyword_names


def test_parallel_script_exposes_runtime_cli_contract():
    tree = _load_tree("backend/scripts/run_parallel_simulation.py")

    assert {"--run-dir", "--run-id", "--seed"} <= _collect_cli_flags(tree)
    assert _has_named_call(tree, "resolve_runtime_dir")
    assert _has_named_call(tree, "apply_runtime_seed")


def test_twitter_script_exposes_runtime_cli_contract():
    tree = _load_tree("backend/scripts/run_twitter_simulation.py")

    assert {"--run-dir", "--run-id", "--seed"} <= _collect_cli_flags(tree)
    assert {"run_dir", "run_id", "runtime_seed"} <= set(
        _get_class_init_args(tree, "TwitterSimulationRunner")
    )
    assert _has_random_seed_call(tree)
    assert {"run_dir", "run_id", "runtime_seed"} <= _constructor_keyword_names(
        tree,
        "TwitterSimulationRunner",
    )


def test_reddit_script_exposes_runtime_cli_contract():
    tree = _load_tree("backend/scripts/run_reddit_simulation.py")

    assert {"--run-dir", "--run-id", "--seed"} <= _collect_cli_flags(tree)
    assert {"run_dir", "run_id", "runtime_seed"} <= set(
        _get_class_init_args(tree, "RedditSimulationRunner")
    )
    assert _has_random_seed_call(tree)
    assert {"run_dir", "run_id", "runtime_seed"} <= _constructor_keyword_names(
        tree,
        "RedditSimulationRunner",
    )
