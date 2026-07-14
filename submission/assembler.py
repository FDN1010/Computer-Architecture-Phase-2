import sys
import os
from typing import Dict, List, Tuple, Optional

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # Fallback to built-in tables if PyYAML is unavailable


# Minimal built-in instruction map fallback (RV32I)
FALLBACK_INSTRUCTIONS: Dict[str, Dict[str, str]] = {
    # R-type
    "add": {"type": "R", "opcode": "0110011", "funct3": "000", "funct7": "0000000"},
    "sub": {"type": "R", "opcode": "0110011", "funct3": "000", "funct7": "0100000"},
    "sll": {"type": "R", "opcode": "0110011", "funct3": "001", "funct7": "0000000"},
    "slt": {"type": "R", "opcode": "0110011", "funct3": "010", "funct7": "0000000"},
    "sltu": {"type": "R", "opcode": "0110011", "funct3": "011", "funct7": "0000000"},
    "xor": {"type": "R", "opcode": "0110011", "funct3": "100", "funct7": "0000000"},
    "srl": {"type": "R", "opcode": "0110011", "funct3": "101", "funct7": "0000000"},
    "sra": {"type": "R", "opcode": "0110011", "funct3": "101", "funct7": "0100000"},
    "or":  {"type": "R", "opcode": "0110011", "funct3": "110", "funct7": "0000000"},
    "and": {"type": "R", "opcode": "0110011", "funct3": "111", "funct7": "0000000"},

    # I-type alu
    "addi": {"type": "I", "opcode": "0010011", "funct3": "000"},
    "slti": {"type": "I", "opcode": "0010011", "funct3": "010"},
    "sltiu": {"type": "I", "opcode": "0010011", "funct3": "011"},
    "xori": {"type": "I", "opcode": "0010011", "funct3": "100"},
    "ori":  {"type": "I", "opcode": "0010011", "funct3": "110"},
    "andi": {"type": "I", "opcode": "0010011", "funct3": "111"},
    "slli": {"type": "I", "opcode": "0010011", "funct3": "001", "funct7": "0000000"},
    "srli": {"type": "I", "opcode": "0010011", "funct3": "101", "funct7": "0000000"},
    "srai": {"type": "I", "opcode": "0010011", "funct3": "101", "funct7": "0100000"},

    # I-type load
    "lb": {"type": "I", "opcode": "0000011", "funct3": "000"},
    "lh": {"type": "I", "opcode": "0000011", "funct3": "001"},
    "lw": {"type": "I", "opcode": "0000011", "funct3": "010"},
    "lbu": {"type": "I", "opcode": "0000011", "funct3": "100"},
    "lhu": {"type": "I", "opcode": "0000011", "funct3": "101"},

    # I-type other
    "jalr": {"type": "I", "opcode": "1100111", "funct3": "000"},
    "ebreak": {"type": "I", "opcode": "1110011", "funct3": "000"},

    # S-type
    "sb": {"type": "S", "opcode": "0100011", "funct3": "000"},
    "sh": {"type": "S", "opcode": "0100011", "funct3": "001"},
    "sw": {"type": "S", "opcode": "0100011", "funct3": "010"},

    # B-type
    "beq": {"type": "B", "opcode": "1100011", "funct3": "000"},
    "bne": {"type": "B", "opcode": "1100011", "funct3": "001"},
    "blt": {"type": "B", "opcode": "1100011", "funct3": "100"},
    "bge": {"type": "B", "opcode": "1100011", "funct3": "101"},
    "bltu": {"type": "B", "opcode": "1100011", "funct3": "110"},
    "bgeu": {"type": "B", "opcode": "1100011", "funct3": "111"},

    # U-type
    "lui":   {"type": "U", "opcode": "0110111"},
    "auipc": {"type": "U", "opcode": "0010111"},

    # J-type
    "jal": {"type": "J", "opcode": "1101111"},
}


# Register mapping (xN and ABI names)
REGS: Dict[str, int] = {
    **{f"x{i}": i for i in range(32)},
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7,
    "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14,
    "a5": 15, "a6": 16, "a7": 17,
    "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22,
    "s7": 23, "s8": 24, "s9": 25, "s10": 26, "s11": 27,
    "t3": 28, "t4": 29, "t5": 30, "t6": 31,
}


def bits_to_int(bits) -> int:
    return int(bits, 2)


def sign_extend(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def parse_yaml(path: str) -> Optional[Dict[str, Dict[str, str]]]:
    if yaml is None:
        return None
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def get_instruction_table(path: str) -> Dict[str, Dict[str, str]]:
    table = parse_yaml(path)
    if not isinstance(table, dict):
        return FALLBACK_INSTRUCTIONS

    # Normalize keys to lowercase.
    norm = {}
    for k, v in table.items():
        if isinstance(v, dict):
            norm[k.lower()] = {kk: vv for kk, vv in v.items()}

    # YAML entries override fallback entries.
    # Make sure binary fields in instructions.yaml are quoted, e.g. opcode: "0110111".
    merged = {**FALLBACK_INSTRUCTIONS, **norm}

    # Ensure all opcode/funct values are strings for bits_to_int.
    for _k, v in merged.items():
        if 'opcode' in v and isinstance(v['opcode'], int):
            v['opcode'] = format(v['opcode'], '07b')
        if 'funct3' in v and isinstance(v['funct3'], int):
            v['funct3'] = format(v['funct3'], '03b')
        if 'funct7' in v and isinstance(v['funct7'], int):
            v['funct7'] = format(v['funct7'], '07b')
    return merged


# Encoders for each instruction type
def encode_r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def encode_i(imm: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    imm &= 0xFFF
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def encode_s(imm: int, rs2: int, rs1: int, funct3: int, opcode: int) -> int:
    imm &= 0xFFF
    imm_high = (imm >> 5) & 0x7F
    imm_low = imm & 0x1F
    return (
        (imm_high << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | (imm_low << 7)
        | (opcode & 0x7F)
    )


def encode_b(offset: int, rs2: int, rs1: int, funct3: int, opcode: int) -> int:
    if offset % 2 != 0:
        raise ValueError("Branch target not halfword-aligned")
    imm = offset
    bit12 = (imm >> 12) & 0x1
    bit11 = (imm >> 11) & 0x1
    bits10_5 = (imm >> 5) & 0x3F
    bits4_1 = (imm >> 1) & 0xF
    return (
        (bit12 << 31)
        | (bits10_5 << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | (bits4_1 << 8)
        | (bit11 << 7)
        | (opcode & 0x7F)
    )


def encode_u(imm20: int, rd: int, opcode: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def encode_j(offset: int, rd: int, opcode: int) -> int:
    if offset % 2 != 0:
        raise ValueError("JAL target not halfword-aligned")
    imm = offset
    bit20 = (imm >> 20) & 0x1
    bits10_1 = (imm >> 1) & 0x3FF
    bit11 = (imm >> 11) & 0x1
    bits19_12 = (imm >> 12) & 0xFF
    return (
        (bit20 << 31)
        | (bits19_12 << 12)
        | (bit11 << 20)
        | (bits10_1 << 21)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def reg_num(tok: str) -> int:
    t = tok.strip().lower()
    if t not in REGS:
        raise ValueError(f"Unknown register: {tok}")
    return REGS[t]


def parse_offset_base(operand: str) -> Tuple[int, int]:
    op = operand.strip()
    if '(' not in op or not op.endswith(')'):
        raise ValueError(f"Expected offset(base) but got '{operand}'")
    imm_str, base_str = op.split('(')
    base_str = base_str[:-1]
    imm = parse_imm(imm_str.strip())
    base = reg_num(base_str.strip())
    return imm, base


def parse_imm(tok: str) -> int:
    t = tok.strip()
    neg = False
    if t.startswith('-'):
        neg = True
        t = t[1:]
    if t.startswith('0x') or t.startswith('0X'):
        val = int(t, 16)
    elif t.startswith('%'):
        raise ValueError("Relocation immediate should be pre-resolved: " + tok)
    else:
        val = int(t, 10)
    return -val if neg else val


def parse_operands(operand_str: str) -> List[str]:
    return [p.strip() for p in operand_str.split(',') if p.strip()]


class AsmState:
    def __init__(self):
        # Memory map required by the later processor phases.
        self.text_base = 0x00400000
        self.data_base = 0x10010000

        self.pc = self.text_base
        self.in_text = False
        self.in_data = False
        self.labels: Dict[str, int] = {}
        self.data_labels: Dict[str, int] = {}
        self.text_insts: List[Tuple[int, str, List[str]]] = []
        self.pending_rel_hi: List[Tuple[int, str, int]] = []
        self.symbols: Dict[str, int] = {}
        self.data_cursor = self.data_base
        self.data_values: List[int] = []


def resolve_hi(addr: int) -> int:
    return (addr + 0x800) >> 12


def resolve_lo(addr: int) -> int:
    lo = addr & 0xFFF
    if lo & 0x800:
        lo -= 0x1000
    return lo


def assemble(
    instructions_path: str,
    asm_path: str
) -> Tuple[List[int], Dict[str, int], List[int], List[int], Dict[str, int]]:
    inst_table = get_instruction_table(instructions_path)
    state = AsmState()

    # First pass: collect labels and instructions, allocate data.
    with open(asm_path, 'r') as f:
        for raw in f:
            line = raw.split('#')[0].strip()
            if not line:
                continue

            if line.startswith('.'):
                directive = line.split()[0]

                if directive == '.text':
                    state.in_text = True
                    state.in_data = False
                    state.pc = state.text_base + len(state.text_insts) * 4

                elif directive == '.data':
                    state.in_data = True
                    state.in_text = False

                elif directive == '.globl':
                    pass

                elif directive == '.word':
                    if not state.in_data:
                        raise ValueError('.word outside .data section')

                    payload = line[len(directive):].strip()
                    if not payload:
                        raise ValueError('Malformed .word')

                    values = [v.strip() for v in payload.split(',') if v.strip()]
                    if not values:
                        raise ValueError('Malformed .word')

                    if state.data_cursor % 4 != 0:
                        state.data_cursor = (state.data_cursor + 3) & ~3

                    for v in values:
                        val = parse_imm(v)
                        state.data_values.append(val & 0xFFFFFFFF)
                        state.data_cursor += 4

                else:
                    pass

                continue

            # Label handling.
            if ':' in line:
                label, rest = line.split(':', 1)
                name = label.strip()

                if state.in_text:
                    addr = state.text_base + len(state.text_insts) * 4
                    state.labels[name] = addr

                elif state.in_data:
                    if state.data_cursor % 4 != 0:
                        state.data_cursor = (state.data_cursor + 3) & ~3
                    state.data_labels[name] = state.data_cursor

                line = rest.strip()
                if not line:
                    continue

            # Instruction line.
            if not state.in_text:
                continue

            if ' ' in line:
                mnemonic, ops = line.split(None, 1)
                operands = parse_operands(ops)
            else:
                mnemonic, operands = line, []

            state.text_insts.append(
                (state.text_base + len(state.text_insts) * 4, mnemonic.lower(), operands)
            )

    symbols = {**state.labels, **state.data_labels}
    state.symbols = symbols

    # Second pass: encode.
    machine: List[int] = []
    for _idx, (addr, mnem, ops) in enumerate(state.text_insts):
        spec = inst_table.get(mnem)
        if spec is None:
            raise ValueError(f"Unknown instruction mnemonic: {mnem}")

        ocode = bits_to_int(spec['opcode'])
        itype = spec['type']

        if itype == 'R':
            if len(ops) != 3:
                raise ValueError(f"{mnem} expects 3 operands")
            rd = reg_num(ops[0])
            rs1 = reg_num(ops[1])
            rs2 = reg_num(ops[2])
            funct3 = bits_to_int(spec['funct3'])
            funct7 = bits_to_int(spec['funct7'])
            inst = encode_r(funct7, rs2, rs1, funct3, rd, ocode)

        elif itype == 'I':
            if mnem == 'ebreak':
                if len(ops) != 0:
                    raise ValueError("ebreak expects no operands")
                inst = 0x00100073

            elif mnem in ('lb', 'lh', 'lw', 'lbu', 'lhu'):
                if len(ops) != 2:
                    raise ValueError(f"{mnem} expects rd, imm(rs1)")
                rd = reg_num(ops[0])
                imm, rs1 = parse_offset_base(ops[1])
                funct3 = bits_to_int(spec['funct3'])
                inst = encode_i(sign_extend(imm, 12), rs1, funct3, rd, ocode)

            elif mnem in ('slli', 'srli', 'srai'):
                if len(ops) != 3:
                    raise ValueError(f"{mnem} expects rd, rs1, shamt")
                rd = reg_num(ops[0])
                rs1 = reg_num(ops[1])
                shamt = parse_imm(ops[2])
                funct3 = bits_to_int(spec['funct3'])
                funct7 = bits_to_int(spec['funct7'])
                imm = ((funct7 & 0x7F) << 5) | (shamt & 0x1F)
                inst = encode_i(imm, rs1, funct3, rd, ocode)

            elif mnem == 'jalr':
                if len(ops) == 2:
                    rd = 1
                    if '(' in ops[1]:
                        imm, rs1 = parse_offset_base(ops[1])
                    else:
                        imm = parse_imm(ops[1])
                        rs1 = reg_num(ops[0])
                elif len(ops) == 3:
                    rd = reg_num(ops[0])
                    rs1 = reg_num(ops[1])
                    imm = parse_imm(ops[2])
                else:
                    raise ValueError("jalr expects rd, rs1, imm or rd, imm(rs1)")
                inst = encode_i(sign_extend(imm, 12), rs1, 0, rd, ocode)

            else:
                if len(ops) != 3:
                    raise ValueError(f"{mnem} expects rd, rs1, imm")
                rd = reg_num(ops[0])
                rs1 = reg_num(ops[1])
                imm_tok = ops[2]

                if imm_tok.startswith('%lo(') and imm_tok.endswith(')'):
                    sym = imm_tok[4:-1]
                    addr_sym = symbols.get(sym)
                    if addr_sym is None:
                        raise ValueError(f"Unknown symbol in %lo(): {sym}")
                    imm = resolve_lo(addr_sym)

                elif imm_tok.startswith('%hi(') and imm_tok.endswith(')'):
                    sym = imm_tok[4:-1]
                    addr_sym = symbols.get(sym)
                    if addr_sym is None:
                        raise ValueError(f"Unknown symbol in %hi(): {sym}")
                    imm = resolve_hi(addr_sym)

                else:
                    imm = parse_imm(imm_tok)

                funct3 = bits_to_int(spec['funct3'])
                inst = encode_i(sign_extend(imm, 12), rs1, funct3, rd, ocode)

        elif itype == 'S':
            if len(ops) != 2:
                raise ValueError(f"{mnem} expects rs2, imm(rs1)")
            rs2 = reg_num(ops[0])
            imm, rs1 = parse_offset_base(ops[1])
            funct3 = bits_to_int(spec['funct3'])
            inst = encode_s(sign_extend(imm, 12), rs2, rs1, funct3, ocode)

        elif itype == 'B':
            if len(ops) != 3:
                raise ValueError(f"{mnem} expects rs1, rs2, label")
            rs1 = reg_num(ops[0])
            rs2 = reg_num(ops[1])
            label = ops[2]
            if label not in symbols:
                raise ValueError(f"Unknown label: {label}")
            target = symbols[label]
            offset = target - addr
            inst = encode_b(offset, rs2, rs1, bits_to_int(spec['funct3']), ocode)

        elif itype == 'U':
            if len(ops) != 2:
                raise ValueError(f"{mnem} expects rd, imm20")
            rd = reg_num(ops[0])
            imm_tok = ops[1]

            if imm_tok.startswith('%hi(') and imm_tok.endswith(')'):
                sym = imm_tok[4:-1]
                addr_sym = symbols.get(sym)
                if addr_sym is None:
                    raise ValueError(f"Unknown symbol in %hi(): {sym}")
                imm20 = resolve_hi(addr_sym)
            else:
                imm20 = parse_imm(imm_tok)

            inst = encode_u(imm20, rd, ocode)

        elif itype == 'J':
            if len(ops) == 1:
                rd = 1
                label = ops[0]
            elif len(ops) == 2:
                rd = reg_num(ops[0])
                label = ops[1]
            else:
                raise ValueError("jal expects rd,label or label")

            if label not in symbols:
                raise ValueError(f"Unknown label: {label}")

            target = symbols[label]
            offset = target - addr
            inst = encode_j(offset, rd, ocode)

        else:
            raise ValueError(f"Unsupported instruction type: {itype}")

        machine.append(inst & 0xFFFFFFFF)

    instruction_addresses = [addr for addr, _mnem, _ops in state.text_insts]

    return machine, symbols, state.data_values, instruction_addresses, state.data_labels


def write_outputs(
    machine: List[int],
    asm_path: str,
    data_values: List[int],
    instruction_addresses: List[int],
    data_labels: Dict[str, int]
) -> Tuple[str, str, str, str, str, str]:
    base_name = os.path.splitext(os.path.basename(asm_path))[0]

    # Output layout used for local/autograder comparison:
    # same folder as .s file/source/gen/
    gen_dir = os.path.join(os.path.dirname(asm_path), "gen")
    os.makedirs(gen_dir, exist_ok=True)

    base = os.path.join(gen_dir, base_name)

    bin_path = base + '.bin'
    txt_path = base + '.hex.txt'

    data_bin_path = base + '_data.bin'
    data_hex_path = base + '_data.hex.txt'
    instruction_addr_path = base + '_instruction_addresses.txt'
    data_addr_path = base + '_data_addresses.txt'

    # Instruction binary output.
    with open(bin_path, 'wb') as bf:
        for w in machine:
            bf.write(w.to_bytes(4, byteorder='little', signed=False))

    # Instruction hex output.
    with open(txt_path, 'w') as tf:
        for w in machine:
            tf.write(f"0x{w:08x}\n")

    # Data binary output: byte-addressable binary.
    with open(data_bin_path, 'wb') as df:
        for w in data_values:
            df.write(w.to_bytes(4, byteorder='little', signed=False))

    # Data hex output: word-addressable hex.
    with open(data_hex_path, 'w') as hf:
        for w in data_values:
            hf.write(f"0x{w:08x}\n")

    # Instruction addresses.
    with open(instruction_addr_path, 'w') as iaf:
        for addr in instruction_addresses:
            iaf.write(f"0x{addr:08x}\n")

    # Data addresses.
    with open(data_addr_path, 'w') as daf:
        for label, addr in data_labels.items():
            daf.write(f"{label}: 0x{addr:08x}\n")

    return (
        bin_path,
        txt_path,
        data_bin_path,
        data_hex_path,
        instruction_addr_path,
        data_addr_path
    )


def main():
    if len(sys.argv) != 3:
        print("Usage: python assembler.py <base_path> <assembly_file>")
        sys.exit(1)

    base_path = sys.argv[1]
    assembly_file = sys.argv[2]
    instructions_yaml = os.path.join(base_path, 'instructions.yaml')

    machine, _symbols, data_values, instruction_addresses, data_labels = assemble(
        instructions_yaml,
        assembly_file
    )

    write_outputs(
        machine,
        assembly_file,
        data_values,
        instruction_addresses,
        data_labels
    )


if __name__ == "__main__":
    main()
