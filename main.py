import re
import subprocess
import sys

# prog = """
# fn strlen(s)
#   i = 0
#   for s[i] != 0
#     i = i + 1
#   end
#   ret i
# end
#
# fn main()
#   msg = "Hello World"
#   len = strlen msg
#   ret len
# end
# """

def preprocess_and_import(source, defines=None, included=None):
    """Preprocess and expand imports together, so defines work across files"""
    if defines is None:
        defines = {}
    if included is None:
        included = set()

    result = []
    cond_stack = []  # stack of (active, seen_true) tuples

    for line in source.split("\n"):
        stripped = line.strip()

        # Check if we're in an inactive conditional block
        active = all(c[0] for c in cond_stack) if cond_stack else True

        if stripped.startswith("#define "):
            if active:
                rest = stripped[8:].strip()
                parts = rest.split(None, 1)
                name = parts[0]
                value = parts[1] if len(parts) > 1 else ""
                defines[name] = value
            continue

        elif stripped.startswith("#undef "):
            if active:
                name = stripped[7:].strip()
                defines.pop(name, None)
            continue

        elif stripped.startswith("#ifdef "):
            name = stripped[7:].strip()
            is_defined = name in defines
            cond_stack.append((active and is_defined, is_defined))
            continue

        elif stripped.startswith("#ifndef "):
            name = stripped[8:].strip()
            is_defined = name in defines
            cond_stack.append((active and not is_defined, not is_defined))
            continue

        elif stripped == "#else":
            if cond_stack:
                prev_active, seen_true = cond_stack.pop()
                parent_active = all(c[0] for c in cond_stack) if cond_stack else True
                cond_stack.append((parent_active and not seen_true, True))
            continue

        elif stripped == "#endif":
            if cond_stack:
                cond_stack.pop()
            continue

        # Handle imports - process with current defines
        elif active and stripped.startswith("import "):
            rest = stripped[7:].strip()
            if rest.startswith('"') and rest.endswith('"'):
                filename = rest[1:-1]
            else:
                filename = rest

            if filename not in included:
                included.add(filename)
                with open(filename) as f:
                    imported = f.read()
                # Recursively process import with current defines
                imported_result = preprocess_and_import(imported, defines, included)
                result.append(imported_result)
            continue

        # Regular line - include if active, with macro substitution
        if active:
            for name, value in defines.items():
                if value:
                    line = line.replace(name, value)
            result.append(line)

    return "\n".join(result)


file = open(sys.argv[1])
prog = preprocess_and_import(file.read())

# --- Scanner ---
pos = 0


def peek():
    return prog[pos] if pos < len(prog) else ""


def advance():
    global pos
    c = peek()
    pos += 1
    return c


def skip_ws():
    while peek() in " \t":
        advance()


def skip_line():
    while peek() and peek() != "\n":
        advance()
    if peek() == "\n":
        advance()


def read_word():
    result = ""
    while peek().isalnum() or peek() == "_":
        result += advance()
    return result


def read_number():
    result = ""
    while peek().isdigit():
        result += advance()
    return result


def eval_const_expr(expr):
    """Evaluate a constant expression like 1024*4 or 64+128"""
    # Simple recursive descent parser for +, -, *, /, ()
    expr = expr.replace(" ", "")
    pos = [0]  # use list for nonlocal mutation

    def peek_char():
        return expr[pos[0]] if pos[0] < len(expr) else ""

    def advance_char():
        c = peek_char()
        pos[0] += 1
        return c

    def parse_number():
        result = ""
        while peek_char().isdigit():
            result += advance_char()
        return int(result) if result else 0

    def parse_factor():
        if peek_char() == "(":
            advance_char()  # skip (
            result = parse_expr()
            advance_char()  # skip )
            return result
        return parse_number()

    def parse_term():
        left = parse_factor()
        while peek_char() and peek_char() in "*/":
            op = advance_char()
            right = parse_factor()
            if op == "*":
                left *= right
            else:
                left //= right
        return left

    def parse_expr():
        left = parse_term()
        while peek_char() and peek_char() in "+-":
            op = advance_char()
            right = parse_term()
            if op == "+":
                left += right
            else:
                left -= right
        return left

    return parse_expr()


def read_string():
    advance()  # skip opening "
    result = ""
    while peek() and peek() != '"':
        if peek() == "\\":
            advance()
            c = advance()
            if c == "n":
                result += "\n"
            elif c == "t":
                result += "\t"
            elif c == "\\":
                result += "\\"
            elif c == '"':
                result += '"'
            else:
                result += c
        else:
            result += advance()
    advance()  # skip closing "
    return result


def read_params():
    params = []
    skip_ws()
    if peek() != "(":
        return params
    advance()  # skip (
    while True:
        skip_ws()
        if peek() == ")":
            advance()
            break
        if peek().isalpha() or peek() == "_":
            params.append(read_word())
        skip_ws()
        if peek() == ",":
            advance()
    return params


def read_until_newline():
    result = ""
    while peek() and peek() != "\n":
        result += advance()
    if peek() == "\n":
        advance()
    return result


def read_until(delim):
    """Read until delimiter, don't consume it"""
    result = ""
    while peek() and peek() != delim and peek() != "\n":
        result += advance()
    return result


def next_token():
    skip_ws()
    if peek() == "":
        return None
    if peek() == "\n":
        advance()
        return ("nl", None)
    if peek() == '"':
        return ("str", read_string())
    if peek().isalpha() or peek() == "_":
        return ("word", read_word())
    if peek().isdigit():
        return ("num", read_number())
    if peek() in "+-*/":
        return ("op", advance())
    if peek() == "[":
        advance()
        return ("lbracket", None)
    if peek() == "]":
        advance()
        return ("rbracket", None)
    if peek() == "&":
        advance()
        skip_ws()
        var_name = read_word()
        return ("addr", var_name)
    if peek() == "@":
        advance()
        skip_ws()
        var_name = read_word()
        return ("deref", var_name)
    if peek() in "=<>!":
        c = advance()
        if peek() == "=":
            return ("cmp", c + advance())
        elif c == "=":
            return ("op", c)
        else:
            return ("cmp", c)
    return ("sym", advance())


# --- Compiler state ---
functions = {}  # name -> list of param names
fn_vars = {}  # name -> {var: offset}
fn_stack = {}  # name -> stack size
string_vars = {}  # var name -> label
literal_strings = {}  # content -> label (for anonymous string literals)
strings = []
mem_buffers = []  # (name, size) tuples for .bss section
blocks = []

current_fn = None
vars = {}
stack_size = 0

label_count = 0

arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]


def var_offset(name):
    global stack_size
    if name not in vars:
        stack_size += 8
        vars[name] = stack_size
    return vars[name]


def add_string(name, content):
    label = f"_str{len(strings)}"
    strings.append((label, content))
    string_vars[name] = label


def get_literal_string(content):
    """Get or create a label for a string literal"""
    if content not in literal_strings:
        label = f"_str{len(strings)}"
        strings.append((label, content))
        literal_strings[content] = label
    return literal_strings[content]


def replace_var(match):
    name = match.group(1)
    if name in string_vars:
        return string_vars[name]
    offset = vars[name]
    return f"[rbp - {offset}]"


def load_val(tok, check_index=True):
    """Load value into rax. If check_index, peek for [index]"""
    if tok[0] == "num":
        return f"    mov rax, {tok[1]}"
    elif tok[0] == "addr":
        # &x - get address of variable
        var_name = tok[1]
        if var_name in string_vars:
            return f"    mov rax, {string_vars[var_name]}"
        else:
            off = var_offset(var_name)
            return f"    lea rax, [rbp - {off}]"
    elif tok[0] == "deref":
        # @x - dereference as qword, @x[i] - indexed qword access
        var_name = tok[1]
        asm = []
        # load base pointer
        if var_name in string_vars:
            asm.append(f"    mov rdi, {string_vars[var_name]}")
        else:
            off = var_offset(var_name)
            asm.append(f"    mov rdi, [rbp - {off}]")
        # check for indexed access
        if check_index and peek() == "[":
            advance()  # skip [
            idx_tok = next_token()
            next_token()  # skip ]
            if idx_tok[0] == "num":
                asm.append(f"    mov rax, [rdi + {int(idx_tok[1]) * 8}]")
            else:
                idx_off = var_offset(idx_tok[1])
                asm.append(f"    mov rax, [rbp - {idx_off}]")
                asm.append(f"    mov rax, [rdi + rax*8]")
        else:
            asm.append(f"    mov rax, [rdi]")
        return "\n".join(asm)
    elif tok[0] == "word":
        # check for array access: name[index]
        if check_index and peek() == "[":
            advance()  # skip [
            idx_tok = next_token()
            next_token()  # skip ]
            asm = []
            # load base address
            if tok[1] in string_vars:
                asm.append(f"    mov rdi, {string_vars[tok[1]]}")
            else:
                off = var_offset(tok[1])
                asm.append(f"    mov rdi, [rbp - {off}]")
            # load index
            if idx_tok[0] == "num":
                asm.append(f"    add rdi, {idx_tok[1]}")
            else:
                idx_off = var_offset(idx_tok[1])
                asm.append(f"    mov rax, [rbp - {idx_off}]")
                asm.append(f"    add rdi, rax")
            # load byte
            asm.append(f"    movzx rax, byte [rdi]")
            return "\n".join(asm)
        else:
            off = var_offset(tok[1])
            return f"    mov rax, [rbp - {off}]"
    else:
        return f"    mov rax, 0"


def load_val_rbx(tok, check_index=True):
    """Load value into rbx. If check_index, peek for [index]"""
    if tok[0] == "num":
        return f"    mov rbx, {tok[1]}"
    elif tok[0] == "addr":
        var_name = tok[1]
        if var_name in string_vars:
            return f"    mov rbx, {string_vars[var_name]}"
        else:
            off = var_offset(var_name)
            return f"    lea rbx, [rbp - {off}]"
    elif tok[0] == "deref":
        var_name = tok[1]
        asm = []
        if var_name in string_vars:
            asm.append(f"    mov rsi, {string_vars[var_name]}")
        else:
            off = var_offset(var_name)
            asm.append(f"    mov rsi, [rbp - {off}]")
        if check_index and peek() == "[":
            advance()
            idx_tok = next_token()
            next_token()
            if idx_tok[0] == "num":
                asm.append(f"    mov rbx, [rsi + {int(idx_tok[1]) * 8}]")
            else:
                idx_off = var_offset(idx_tok[1])
                asm.append(f"    mov rbx, [rbp - {idx_off}]")
                asm.append(f"    mov rbx, [rsi + rbx*8]")
        else:
            asm.append(f"    mov rbx, [rsi]")
        return "\n".join(asm)
    elif tok[0] == "word":
        # check for array access
        if check_index and peek() == "[":
            advance()  # skip [
            idx_tok = next_token()
            next_token()  # skip ]
            asm = []
            # load base address
            if tok[1] in string_vars:
                asm.append(f"    mov rsi, {string_vars[tok[1]]}")
            else:
                off = var_offset(tok[1])
                asm.append(f"    mov rsi, [rbp - {off}]")
            # load index
            if idx_tok[0] == "num":
                asm.append(f"    add rsi, {idx_tok[1]}")
            else:
                idx_off = var_offset(idx_tok[1])
                asm.append(f"    mov rbx, [rbp - {idx_off}]")
                asm.append(f"    add rsi, rbx")
            # load byte
            asm.append(f"    movzx rbx, byte [rsi]")
            return "\n".join(asm)
        else:
            off = var_offset(tok[1])
            return f"    mov rbx, [rbp - {off}]"
    else:
        return f"    mov rbx, 0"


def load_arg(tok, reg):
    if tok[0] == "num":
        return f"    mov {reg}, {tok[1]}"
    elif tok[0] == "addr":
        var_name = tok[1]
        if var_name in string_vars:
            return f"    mov {reg}, {string_vars[var_name]}"
        else:
            off = var_offset(var_name)
            return f"    lea {reg}, [rbp - {off}]"
    elif tok[0] == "deref":
        var_name = tok[1]
        asm = []
        if var_name in string_vars:
            asm.append(f"    mov {reg}, {string_vars[var_name]}")
        else:
            off = var_offset(var_name)
            asm.append(f"    mov {reg}, [rbp - {off}]")
        # check for indexed access
        if peek() == "[":
            advance()
            idx_tok = next_token()
            next_token()  # skip ]
            if idx_tok[0] == "num":
                asm.append(f"    mov {reg}, [{reg} + {int(idx_tok[1]) * 8}]")
            else:
                idx_off = var_offset(idx_tok[1])
                asm.append(f"    push rax")
                asm.append(f"    mov rax, [rbp - {idx_off}]")
                asm.append(f"    mov {reg}, [{reg} + rax*8]")
                asm.append(f"    pop rax")
        else:
            asm.append(f"    mov {reg}, [{reg}]")
        return "\n".join(asm)
    elif tok[1] in string_vars:
        return f"    mov {reg}, {string_vars[tok[1]]}"
    else:
        off = var_offset(tok[1])
        return f"    mov {reg}, [rbp - {off}]"


def parse_call(fn_name):
    """Parse function call arguments and emit call code"""
    asm = []
    args = []

    def collect_arg(tok):
        """Process a token and return an arg tuple"""
        if tok[0] == "str":
            # string literal - get or create label
            label = get_literal_string(tok[1])
            return ("strlit", label)
        elif tok[0] in ("deref", "addr"):
            idx = None
            if peek() == "[":
                advance()
                idx_tok = next_token()
                next_token()  # skip ]
                idx = idx_tok[1] if idx_tok else None
            return (tok[0], tok[1], idx)
        elif tok[0] == "word" and tok[1] in functions:
            # nested function call - parse it recursively
            inner_asm = parse_call(tok[1])
            return ("call_result", inner_asm)
        else:
            return tok

    # check for parentheses syntax: fn(a, b)
    skip_ws()
    if peek() == "(":
        advance()  # skip (
        while True:
            skip_ws()
            if peek() == ")":
                advance()
                break
            tok = next_token()
            if tok and tok[0] in ("num", "word", "addr", "deref", "str"):
                args.append(collect_arg(tok))
            skip_ws()
            if peek() == ",":
                advance()
    else:
        # space-separated: fn a b
        while True:
            tok = next_token()
            if tok is None or tok[0] == "nl":
                break
            if tok[0] == "lbracket":
                continue
            if tok[0] in ("num", "word", "addr", "deref", "str"):
                args.append(collect_arg(tok))

    # Handle nested calls first - emit their code and push results
    nested_indices = []
    for i, arg in enumerate(args):
        if arg[0] == "call_result":
            asm.append(arg[1])  # emit the nested call
            asm.append("    push rax")  # save result
            nested_indices.append(i)

    # Pop nested results in reverse order and load into correct regs
    # But first, load simple args
    for i, arg in enumerate(args):
        if arg[0] != "call_result":
            asm.append(load_arg_ext(arg, arg_regs[i]))

    # Now pop nested call results into their registers (reverse order)
    for i in reversed(nested_indices):
        asm.append(f"    pop {arg_regs[i]}")

    asm.append(f"    call {fn_name}")
    return "\n".join(asm)


def load_arg_ext(tok, reg):
    """Load arg into register, handling extended tuples for indexed deref/addr"""
    if tok[0] == "strlit":
        # string literal - tok[1] is the label
        return f"    mov {reg}, {tok[1]}"
    elif tok[0] == "call_result":
        # handled separately via push/pop
        return ""
    elif len(tok) == 3 and tok[0] in ("deref", "addr"):
        var_name = tok[1]
        idx = tok[2]
        if tok[0] == "deref":
            asm = []
            if var_name in string_vars:
                asm.append(f"    mov {reg}, {string_vars[var_name]}")
            else:
                off = var_offset(var_name)
                asm.append(f"    mov {reg}, [rbp - {off}]")
            if idx is not None:
                asm.append(f"    mov {reg}, [{reg} + {int(idx) * 8}]")
            else:
                asm.append(f"    mov {reg}, [{reg}]")
            return "\n".join(asm)
        else:  # addr
            if var_name in string_vars:
                return f"    mov {reg}, {string_vars[var_name]}"
            else:
                off = var_offset(var_name)
                return f"    lea {reg}, [rbp - {off}]"
    else:
        return load_arg(tok, reg)


def parse_expr(first_tok):
    # check if it's a function call
    if first_tok[0] == "word" and first_tok[1] in functions:
        return parse_call(first_tok[1])

    # normal expression
    asm = [load_val(first_tok)]
    while True:
        tok = next_token()
        if tok is None or tok[0] == "nl":
            break
        if tok[0] == "op":
            right = next_token()
            match tok[1]:
                case "+":
                    asm.append(load_val_rbx(right))
                    asm.append("    add rax, rbx")
                case "-":
                    asm.append(load_val_rbx(right))
                    asm.append("    sub rax, rbx")
                case "*":
                    asm.append(load_val_rbx(right))
                    asm.append("    imul rax, rbx")
                case "/":
                    asm.append("    xor rdx, rdx")
                    asm.append(load_val_rbx(right))
                    asm.append("    idiv rbx")
    return "\n".join(asm)


# --- First pass: collect functions, variables and strings ---
while pos < len(prog):
    # skip asm block contents
    if blocks and blocks[-1] == "asm":
        skip_ws()
        if peek() == "\n":
            advance()
            continue
        line = read_until_newline().strip()
        if line == "end":
            blocks.pop()
        continue

    # handle mem block contents
    if blocks and blocks[-1] == "mem":
        skip_ws()
        if peek() == "\n":
            advance()
            continue
        name = read_word()
        if name == "end":
            blocks.pop()
            skip_line()
            continue
        skip_ws()
        # read size expression until newline
        size_expr = read_until("\n").strip()
        if name and size_expr:
            size = eval_const_expr(size_expr)
            mem_buffers.append((name, size))
        skip_line()
        continue

    tok = next_token()
    if tok is None:
        break
    if tok[0] == "nl":
        continue

    if tok == ("word", "fn"):
        blocks.append("fn")
        skip_ws()
        name = read_word()
        params = read_params()
        functions[name] = params
        current_fn = name
        vars = {}
        stack_size = 0
        # params are variables too
        for p in params:
            var_offset(p)
        skip_line()
        continue

    if tok == ("word", "if"):
        blocks.append("if")
        skip_line()
        continue

    if tok == ("word", "else"):
        skip_line()
        continue

    if tok == ("word", "mem"):
        skip_ws()
        if peek() == "\n":
            # block style: mem\n  name size\n  ...\nend
            blocks.append("mem")
            skip_line()
            continue
        # single line: mem name size_expr
        name = read_word()
        skip_ws()
        size_expr = read_until("\n").strip()
        if name and size_expr:
            size = eval_const_expr(size_expr)
            mem_buffers.append((name, size))
        skip_line()
        continue

    if tok == ("word", "for"):
        blocks.append("for")
        # check for C-style init variable
        skip_ws()
        start_pos = pos
        line = read_until("\n")
        if ";" in line:
            # C-style: extract init var
            init_part = line.split(";")[0].strip()
            init_tokens = init_part.split()
            if len(init_tokens) >= 3 and init_tokens[1] == "=":
                var_offset(init_tokens[0])
        pos = start_pos
        skip_line()
        continue

    if tok == ("word", "end"):
        if blocks:
            block = blocks.pop()
            if block == "fn":
                fn_vars[current_fn] = vars.copy()
                fn_stack[current_fn] = stack_size
                current_fn = None
        skip_line()
        continue

    if tok == ("word", "asm"):
        blocks.append("asm")
        skip_line()
        continue

    if tok[0] == "word" and tok[1] == "ret":
        skip_line()
        continue

    if tok[0] == "word":
        name = tok[1]
        tok2 = next_token()
        if tok2 and tok2 == ("op", "="):
            tok3 = next_token()
            if tok3 and tok3[0] == "str":
                add_string(name, tok3[1])
            elif tok3 and tok3[0] in ("num", "word"):
                var_offset(name)
        skip_line()

# Register mem buffer names so they can be used like string labels
for name, size in mem_buffers:
    string_vars[name] = name

# --- Second pass: generate code ---
pos = 0
out = []
blocks = []
current_fn = None

# Note: .data section will be prepended after code generation
# so that string literals from parse_call are included

out.append("section .text")
out.append("")

fn_end = """\
    mov rsp, rbp
    pop rbp
    mov rax, 0
    ret"""

while pos < len(prog):
    if blocks and blocks[-1] == "asm":
        skip_ws()
        if peek() == "\n":
            advance()
            continue
        line = read_until_newline().strip()
        if line == "end":
            blocks.pop()
        else:
            line = re.sub(r"\$(\w+)", replace_var, line)
            out.append("    " + line)
        continue

    tok = next_token()
    if tok is None:
        break
    if tok[0] == "nl":
        continue

    match tok:
        case ("word", "fn"):
            blocks.append("fn")
            skip_ws()
            name = read_word()
            params = read_params()
            current_fn = name
            vars = fn_vars[name]
            stack_size = fn_stack[name]

            out.append(f"global {name}")
            out.append(f"{name}:")
            out.append("    push rbp")
            out.append("    mov rbp, rsp")
            out.append(f"    sub rsp, {stack_size}")

            # copy args from registers to stack
            for i, p in enumerate(params):
                off = vars[p]
                out.append(f"    mov [rbp - {off}], {arg_regs[i]}")

            skip_line()

        case ("word", "if"):
            left = next_token()
            cmp_op = next_token()
            right = next_token()
            skip_line()

            out.append(load_val(left))
            out.append(load_val_rbx(right))
            out.append("    cmp rax, rbx")

            else_label = f".if_else_{label_count}"
            end_label = f".if_end_{label_count}"
            label_count += 1

            jump = {
                "<": "jge",
                ">": "jle",
                "==": "jne",
                "!=": "je",
                "<=": "jg",
                ">=": "jl",
            }
            out.append(f"    {jump[cmp_op[1]]} {else_label}")

            blocks.append(("if", else_label, end_label))

        case ("word", "ret"):
            first = next_token()
            expr_asm = parse_expr(first)
            out.append(expr_asm)
            out.append("    mov rsp, rbp")
            out.append("    pop rbp")
            out.append("    ret")

        case ("word", "asm"):
            blocks.append("asm")
            skip_line()

        case ("word", "for"):
            # peek ahead to see if C-style (has ;) or while-style
            start_pos = pos
            line = read_until("\n")
            pos = start_pos  # reset to parse properly

            start_label = f".for_start_{label_count}"
            end_label = f".for_end_{label_count}"
            label_count += 1

            if ";" in line:
                # C-style: init; cond; post
                # parse init
                init_part = read_until(";")
                advance()  # skip ;
                skip_ws()

                # parse condition
                cond_left = next_token()
                cond_left_idx = None
                t = next_token()
                if t == ("lbracket", None):
                    cond_left_idx = next_token()
                    next_token()  # skip ]
                    cond_op = next_token()
                else:
                    cond_op = t
                cond_right = next_token()
                skip_ws()
                if peek() == ";":
                    advance()  # skip ;
                skip_ws()

                # parse post
                post_var = next_token()
                post_eq = next_token()  # =
                post_first = next_token()
                post_asm_lines = []
                # parse post expression
                post_asm_lines.append(load_val(post_first))
                while True:
                    t = next_token()
                    if t is None or t[0] == "nl":
                        break
                    if t[0] == "op":
                        right = next_token()
                        match t[1]:
                            case "+":
                                post_asm_lines.append(load_val_rbx(right))
                                post_asm_lines.append("    add rax, rbx")
                            case "-":
                                post_asm_lines.append(load_val_rbx(right))
                                post_asm_lines.append("    sub rax, rbx")
                            case "*":
                                post_asm_lines.append(load_val_rbx(right))
                                post_asm_lines.append("    imul rax, rbx")
                            case "/":
                                post_asm_lines.append("    xor rdx, rdx")
                                post_asm_lines.append(load_val_rbx(right))
                                post_asm_lines.append("    idiv rbx")
                off = var_offset(post_var[1])
                post_asm_lines.append(f"    mov [rbp - {off}], rax")
                post_asm = "\n".join(post_asm_lines)

                # emit init
                init_tokens = init_part.split()
                if len(init_tokens) >= 3 and init_tokens[1] == "=":
                    init_var = init_tokens[0]
                    init_val = init_tokens[2]
                    init_off = var_offset(init_var)
                    out.append(f"    mov rax, {init_val}")
                    out.append(f"    mov [rbp - {init_off}], rax")

                # emit start label
                out.append(f"{start_label}:")

                # emit condition - load left into rax
                if cond_left_idx:
                    # indexed access
                    if cond_left[1] in string_vars:
                        out.append(f"    mov rdi, {string_vars[cond_left[1]]}")
                    else:
                        off = var_offset(cond_left[1])
                        out.append(f"    mov rdi, [rbp - {off}]")
                    if cond_left_idx[0] == "num":
                        out.append(f"    add rdi, {cond_left_idx[1]}")
                    else:
                        idx_off = var_offset(cond_left_idx[1])
                        out.append(f"    mov rax, [rbp - {idx_off}]")
                        out.append(f"    add rdi, rax")
                    out.append(f"    movzx rax, byte [rdi]")
                else:
                    out.append(load_val(cond_left, check_index=False))
                out.append(load_val_rbx(cond_right, check_index=False))
                out.append("    cmp rax, rbx")
                jump = {
                    "<": "jge", ">": "jle", "==": "jne",
                    "!=": "je", "<=": "jg", ">=": "jl",
                }
                out.append(f"    {jump[cond_op[1]]} {end_label}")

                blocks.append(("for", start_label, end_label, post_asm))

            else:
                # while-style: just condition
                cond_left = next_token()
                cond_left_idx = None
                # check for indexed access: s[i]
                t = next_token()
                if t == ("lbracket", None):
                    cond_left_idx = next_token()
                    next_token()  # skip ]
                    cond_op = next_token()
                else:
                    cond_op = t
                cond_right = next_token()
                skip_line()

                # emit start label
                out.append(f"{start_label}:")

                # emit condition - load left into rax
                if cond_left_idx:
                    # indexed access
                    if cond_left[1] in string_vars:
                        out.append(f"    mov rdi, {string_vars[cond_left[1]]}")
                    else:
                        off = var_offset(cond_left[1])
                        out.append(f"    mov rdi, [rbp - {off}]")
                    if cond_left_idx[0] == "num":
                        out.append(f"    add rdi, {cond_left_idx[1]}")
                    else:
                        idx_off = var_offset(cond_left_idx[1])
                        out.append(f"    mov rax, [rbp - {idx_off}]")
                        out.append(f"    add rdi, rax")
                    out.append(f"    movzx rax, byte [rdi]")
                else:
                    out.append(load_val(cond_left, check_index=False))
                out.append(load_val_rbx(cond_right, check_index=False))
                out.append("    cmp rax, rbx")
                jump = {
                    "<": "jge", ">": "jle", "==": "jne",
                    "!=": "je", "<=": "jg", ">=": "jl",
                }
                out.append(f"    {jump[cond_op[1]]} {end_label}")

                blocks.append(("for", start_label, end_label, None))

        case ("word", "else"):
            block = blocks.pop()
            out.append(f"    jmp {block[2]}")  # jump to end
            out.append(f"{block[1]}:")         # else label
            blocks.append(("else", block[2]))  # push end_label for end
            skip_line()

        case ("word", "end"):
            block = blocks.pop()
            if block[0] == "if":
                # no else - else_label is where we land
                out.append(f"{block[1]}:")
            elif block[0] == "else":
                # had else - emit end_label
                out.append(f"{block[1]}:")
            elif block[0] == "for":
                # emit post statement if C-style
                if block[3]:
                    out.append(block[3])
                out.append(f"    jmp {block[1]}")  # jump to start
                out.append(f"{block[2]}:")         # end label
            elif block[0] == "fn":
                out.append(fn_end)
                current_fn = None
            skip_line()

        case ("word", name):
            # check if it's a function call or assignment
            if name in functions:
                # bare function call: print(f)
                call_asm = parse_call(name)
                out.append(call_asm)
            else:
                tok2 = next_token()
                if tok2 == ("lbracket", None):
                    # array assignment: name[index] = value
                    idx_tok = next_token()
                    next_token()  # skip ]
                    next_token()  # skip =
                    val_tok = next_token()
                    skip_line()

                    # compute address: name + index
                    if name in string_vars:
                        out.append(f"    mov rdi, {string_vars[name]}")
                    else:
                        off = var_offset(name)
                        out.append(f"    mov rdi, [rbp - {off}]")

                    if idx_tok[0] == "num":
                        out.append(f"    add rdi, {idx_tok[1]}")
                    else:
                        idx_off = var_offset(idx_tok[1])
                        out.append(f"    mov rax, [rbp - {idx_off}]")
                        out.append(f"    add rdi, rax")

                    # load value
                    if val_tok[0] == "num":
                        out.append(f"    mov byte [rdi], {val_tok[1]}")
                    else:
                        val_off = var_offset(val_tok[1])
                        out.append(f"    mov al, [rbp - {val_off}]")
                        out.append(f"    mov [rdi], al")

                elif tok2 == ("op", "="):
                    tok3 = next_token()
                    if tok3[0] == "str":
                        skip_line()
                    else:
                        expr_asm = parse_expr(tok3)
                        out.append(expr_asm)
                        off = var_offset(name)
                        out.append(f"    mov [rbp - {off}], rax")

        case _:
            skip_line()

# Generate .data section (after code generation so literals are included)
data_section = []
if strings:
    data_section.append("section .data")
    for label, content in strings:
        parts = []
        current = ""
        for c in content:
            if c == "\n":
                if current:
                    parts.append(f'"{current}"')
                parts.append("10")
                current = ""
            elif c == "\t":
                if current:
                    parts.append(f'"{current}"')
                parts.append("9")
                current = ""
            else:
                current += c
        if current:
            parts.append(f'"{current}"')
        parts.append("0")
        data_section.append(f"    {label}: db {', '.join(parts)}")
    data_section.append("")

# Generate .bss section for mem buffers
bss_section = []
if mem_buffers:
    bss_section.append("section .bss")
    for name, size in mem_buffers:
        bss_section.append(f"    {name}: resb {size}")
    bss_section.append("")

# Combine: .data first, then .bss, then .text
asm_out = "\n".join(data_section + bss_section + out)
with open("out.asm", "w") as f:
    f.write(asm_out)
# print(asm_out)
subprocess.run(["nasm", "-felf64", "out.asm", "-o", "out.o"])
subprocess.run(["ld", "out.o", "-o", "out"])
