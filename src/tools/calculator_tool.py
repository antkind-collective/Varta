import ast
import re
import operator as op
from typing import Dict, Any
from src.tools.base_tool import BaseTool

# Safe operators map for AST evaluation
SAFE_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos
}

class CalculatorTool(BaseTool):
    """
    Calculator Tool for safe arithmetic evaluation.
    Evaluates math expressions (addition, subtraction, multiplication, division, powers, percentages)
    using safe AST parsing with zero code execution / eval risks.
    """

    @property
    def tool_name(self) -> str:
        return "calculator"

    @property
    def tool_description(self) -> str:
        return "Safely evaluates arithmetic expressions and percentage calculations without code execution."

    def validate(self, input_data: Dict[str, Any]) -> bool:
        if not isinstance(input_data, dict):
            return False
        expr = input_data.get("expression") or input_data.get("query")
        return bool(expr and isinstance(expr, str) and expr.strip())

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate(input_data):
            return {
                "success": False,
                "error": "Invalid arithmetic expression for CalculatorTool.",
                "answer": "Invalid math expression."
            }

        raw_expr = input_data.get("expression") or input_data.get("query")
        clean_expr = self._preprocess_expression(raw_expr)

        try:
            val = self._safe_eval(clean_expr)
            result_str = str(int(val)) if isinstance(val, float) and val.is_integer() else str(round(val, 6))
            formatted_answer = f"Result of `{raw_expr.strip()}` = **{result_str}**"
            return {
                "success": True,
                "tool_name": self.tool_name,
                "expression": clean_expr,
                "value": val,
                "answer": formatted_answer,
                "confidence": {
                    "score": 1.0,
                    "level": "HIGH",
                    "retrieval_support": "EXACT_CALCULATION",
                    "context_coverage_pct": 100.0
                },
                "citations": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Mathematical evaluation failed: {e}",
                "answer": f"Unable to evaluate mathematical expression: '{raw_expr}'."
            }

    def _preprocess_expression(self, text: str) -> str:
        """
        Converts human-friendly math phrases (e.g. '12% of 800' or 'calculate 25 * 19') to valid math syntax.
        """
        expr = text.strip()
        expr = re.sub(r"^(calculate|what is|eval|compute|find)\s+", "", expr, flags=re.IGNORECASE).strip()
        expr = expr.rstrip("=? ")

        # Convert "X% of Y" -> "(X / 100) * Y"
        expr = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", r"(\1 / 100.0) * \2", expr, flags=re.IGNORECASE)

        # Convert standalone "X%" -> "(X / 100.0)"
        expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1 / 100.0)", expr)

        return expr

    def _safe_eval(self, expr: str) -> float:
        """
        Safely evaluates AST tree for basic mathematical operators.
        """
        tree = ast.parse(expr, mode="eval")

        def _eval_node(node):
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return float(node.value)
                raise ValueError(f"Unsupported constant type: {type(node.value)}")
            elif hasattr(ast, "Num") and isinstance(node, getattr(ast, "Num")):
                return float(node.n)
            elif isinstance(node, ast.BinOp):
                left = _eval_node(node.left)
                right = _eval_node(node.right)
                op_type = type(node.op)
                if op_type in SAFE_OPERATORS:
                    return SAFE_OPERATORS[op_type](left, right)
                raise ValueError(f"Unsupported operator: {op_type}")
            elif isinstance(node, ast.UnaryOp):
                operand = _eval_node(node.operand)
                op_type = type(node.op)
                if op_type in SAFE_OPERATORS:
                    return SAFE_OPERATORS[op_type](operand)
                raise ValueError(f"Unsupported unary operator: {op_type}")
            else:
                raise ValueError(f"Unsupported syntax structure: {type(node)}")

        return _eval_node(tree)
