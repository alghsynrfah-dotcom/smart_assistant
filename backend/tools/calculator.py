
import ast
import operator
import re


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def calculate(expression: str):
    try:
        # Find the mathematical expression inside the question
        match = re.search(
            r"\d+(?:\s*[\+\-\*\/\%]\s*\d+)+",
            expression
        )

        if not match:
            return None

        expression = match.group(0)

        tree = ast.parse(
            expression,
            mode="eval"
        )

        def evaluate(node):

            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value

                raise ValueError("Invalid value")

            if isinstance(node, ast.BinOp):

                operation = OPERATORS.get(
                    type(node.op)
                )

                if operation is None:
                    raise ValueError(
                        "Unsupported operation"
                    )

                left = evaluate(node.left)
                right = evaluate(node.right)

                return operation(left, right)

            if isinstance(node, ast.UnaryOp):

                value = evaluate(node.operand)

                if isinstance(node.op, ast.USub):
                    return -value

                if isinstance(node.op, ast.UAdd):
                    return value

                raise ValueError(
                    "Unsupported operation"
                )

            raise ValueError("Invalid expression")

        return evaluate(tree.body)

    except Exception as e:
        print("CALCULATOR ERROR:", e)
        return None

