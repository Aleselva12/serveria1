import math

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def sin(degrees):
    return math.sin(math.radians(degrees))

def cos(degrees):
    return math.cos(math.radians(degrees))

def tan(degrees):
    return math.tan(math.radians(degrees))

def calculate(expression):
    allowed_names = {"sin": sin, "cos": cos, "tan": tan}
    return eval(expression, {"__builtins__": {}}, allowed_names)

def main():
    print("Simple Calculator")
    print("Operations: +  -  *  /  sin()  cos()  tan()")
    print("Trig functions take degrees, e.g. sin(30)")
    print("Type 'quit' to exit\n")

    while True:
        expr = input("Enter expression (e.g. 2 + 3 or sin(30)): ").strip()
        if expr.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if not expr:
            continue
        try:
            result = calculate(expr)
            print(f"Result: {result}\n")
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()