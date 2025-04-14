import sys
import xml.etree.ElementTree as etree
from _elementtree import ParseError
import time  # Added for timing execution


class Interpreter:

    def __init__(self, input, debug=False):
        self.filename = input  
        self.instructions = []  
        self.vars = {}
        self.debug = debug 
        self.load_file()  
        try:
            self.program = etree.parse(self.filename).getroot()
        except ParseError:
            print('Error during the parsing of XML, invalid XML input or file cannot be opened.', file=sys.stderr)
            exit(3)
        self.variables = {}
        self.variables["True"] = "true"
        self.variables["False"] = "false"
        self.labels = {}
        self.pc = 0
        self.data_stack = []
        self.call_stack = []
        self.execution_time = 0  # Track execution time

    def log_debug(self, message):
        """Print debug message only if debug mode is enabled"""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)

    def load_file(self):
        pass 

    def run(self):
        self.read_labels()
        self.check_args()
        op_method_map = {
            'PRINT': 'print_',
            'RETURN': 'return_',
            'READINT': 'read_int',
            'READSTR': 'readstr',
            'INTSTR': 'intstr',
            'CONCAT': 'concat',
            'LEN': 'len_',
            'GETAT': 'getat',
            'STRBOOL': 'strbool',  
            'JUMPIFGR': 'jumpifgr',
            'JUMPIFEQ': 'jumpifeq',
            'IFGOTO': 'ifgoto',
            'PUSH': 'push',
            'POP': 'pop',
        }
        
        start_time = time.time()
        
        while self.pc < len(self.program):
            op = self.program[self.pc].attrib['opcode']
            self.log_debug(f"Processing operation: {op} at pc={self.pc}")
            
            method_name = op_method_map.get(op, op.lower())
            operation = getattr(self, method_name, None)
            
            if callable(operation):
                self.log_debug(f"Calling method: {method_name}")
                operation(self.program[self.pc])
            else:
                print(f'Semantic Error: Invalid operation "{op}" (method: {method_name} not found).', file=sys.stderr)
                exit(5)
            self.pc += 1
            
        self.execution_time = time.time() - start_time
        return self.execution_time

    def read_labels(self):
        for i, instruction in enumerate(self.program):
            if instruction.attrib['opcode'] == 'LABEL':
                label = instruction.find('dst')
                if label.text in self.labels:
                    print("Semantic Error: Label duplicated", file=sys.stderr)
                    exit(5)
                if label.attrib['kind'] != 'literal' or label.attrib['type'] != 'string':
                    print("Run-time Error: Label must be a literal string.", file=sys.stderr)
                    exit(14)
                self.labels[label.text] = i

    def check_args(self):
        for instruction in self.program:
            if len(instruction.attrib) > 3:
                print('Semantic Error: Too many arguments.', file=sys.stderr)
                exit(5)
            for arg in instruction:
                if arg.tag not in ['src1', 'src2', 'dst']:
                    print("Semantic Error: Invalid argument tag.", file=sys.stderr)
                    exit(5)
                if 'kind' not in arg.attrib:
                    print("Semantic Error: Missing 'kind' attribute.", file=sys.stderr)
                    exit(5)
                if 'type' not in arg.attrib:
                    print("Semantic Error: Missing 'type' attribute.", file=sys.stderr)
                    exit(5)
                if arg.attrib['kind'] == 'variable' and not (arg.text and (not arg.text[0].isdigit()) and all(c.isalnum() or c == '_' for c in arg.text)):
                    print(f"Semantic Error: Invalid variable name '{arg.text}'.", file=sys.stderr)
                    exit(5)

    def get_src_value(self, src):
        if 'kind' not in src.attrib:
            print("Semantic Error: Missing 'kind'.", file=sys.stderr)
            exit(5)
        if src.attrib['kind'] == 'variable':
            if src.text not in self.variables:
                print(f"Run-time Error: Uninitialized variable '{src.text}'.", file=sys.stderr)
                exit(11)
            return self.variables[src.text]
        if 'type' not in src.attrib:
            print("Semantic Error: Missing 'type'.", file=sys.stderr)
            exit(5)
        if src.attrib['type'] == 'integer':
            try:
                return int(src.text)
            except ValueError:
                print("Run-time Error: Invalid integer literal.", file=sys.stderr)
                exit(20)
        if src.text.lower() == "true":
            return True
        elif src.text.lower() == "false":
            return False
        return src.text

    def mov(self, cmd):
        dst, src = cmd.find('dst'), cmd.find('src1')
        if dst is None or src is None:
            print("Semantic Error: Missing argument.", file=sys.stderr)
            exit(5)
        if dst.attrib['kind'] == 'variable':
            self.variables[dst.text] = self.get_src_value(src)
        else:
            print("Run-time Error: MOV destination must be a variable.", file=sys.stderr)
            exit(14)

    def add(self, cmd):
        self.binary_op(cmd, lambda x, y: x + y)

    def sub(self, cmd):
        self.binary_op(cmd, lambda x, y: x - y)

    def mul(self, cmd):
        self.binary_op(cmd, lambda x, y: x * y)

    def div(self, cmd):
        def safe_div(x, y):
            if y == 0:
                print("Run-time Error: Division by zero.", file=sys.stderr)
                exit(12)
            return x // y
        self.binary_op(cmd, safe_div)

    def binary_op(self, cmd, operation):
        dst, src1, src2 = cmd.find('dst'), cmd.find('src1'), cmd.find('src2')
        if None in (dst, src1, src2):
            print("Semantic Error: Missing argument.", file=sys.stderr)
            exit(5)
            
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: Binary operation destination must be a variable.", file=sys.stderr)
            exit(14)
            
        val1 = self.get_src_value(src1)
        val2 = self.get_src_value(src2)
        
        try:
            if isinstance(val1, str) and val1.isdigit():
                val1 = int(val1)
            if isinstance(val2, str) and val2.isdigit():
                val2 = int(val2)
                
            self.log_debug(f"Operating on values: {val1} ({type(val1)}) and {val2} ({type(val2)})")
            
            result = operation(val1, val2)
            self.variables[dst.text] = result
        except (ValueError, TypeError) as e:
            print(f"Run-time Error: Cannot perform operation on these types: {e}", file=sys.stderr)
            exit(14)

    def print_(self, cmd):
        src = cmd.find('src1')
        if src is None:
            print("Semantic Error: PRINT missing source argument.", file=sys.stderr)
            exit(5)
        print(str(self.get_src_value(src)))

    def read_int(self, cmd):
        dst = cmd.find('dst')
        if dst is None:
            print("Semantic Error: READINT missing destination.", file=sys.stderr)
            exit(5)
        if dst.attrib['kind'] == 'variable' and dst.attrib['type'] == 'integer':
            try:
                self.variables[dst.text] = int(input(f"{dst.text} = "))
            except ValueError:
                print("Run-time Error: Invalid integer input.", file=sys.stderr)
                exit(13)
        else:
            print("Run-time Error: READINT requires integer variable.", file=sys.stderr)
            exit(14)

    def readstr(self, cmd):
        dst = cmd.find('dst')
        if dst is None:
            print("Semantic Error: READSTR missing destination.", file=sys.stderr)
            exit(5)
        if dst.attrib['kind'] == 'variable':
            self.variables[dst.text] = input(f"{dst.text} = ")
        else:
            print("Run-time Error: READSTR destination must be a variable.", file=sys.stderr)
            exit(14)

    def label(self, cmd):
        pass

    def jump(self, cmd):
        self._jump_common(cmd, always_jump=True)

    def jumpifeq(self, cmd):
        if self._compare_args(cmd, lambda x, y: x == y):
            self._jump_common(cmd)

    def jumpifgr(self, cmd):
        if self._compare_args(cmd, lambda x, y: x > y):
            self._jump_common(cmd)

    def ifgoto(self, cmd):
        dst, src1, src2 = cmd.find('dst'), cmd.find('src1'), cmd.find('src2')
        if None in (dst, src1, src2):
            print("Semantic Error: IFGOTO operation missing argument.", file=sys.stderr)
            exit(5)
        
        if dst.attrib['kind'] != 'literal' or dst.attrib['type'] != 'string':
            print("Run-time Error: IFGOTO requires a label as destination.", file=sys.stderr)
            exit(14)
            
        val1 = self.get_src_value(src1)
        val2 = self.get_src_value(src2)
        
        if val1 <= val2:
            if dst.text not in self.labels:
                print(f"Run-time Error: Label '{dst.text}' not found.", file=sys.stderr)
                exit(10)
            self.pc = self.labels[dst.text] - 1  

    def _compare_args(self, cmd, comparator):
        dst, src1, src2 = cmd.find('dst'), cmd.find('src1'), cmd.find('src2')
        if None in (dst, src1, src2):
            print("Semantic Error: JUMPIF operation missing argument.", file=sys.stderr)
            exit(5)
            
        if dst.attrib['type'] != 'string' or dst.attrib['kind'] != 'literal':
            print("Run-time Error: JUMPIF destination must be a label (literal string).", file=sys.stderr)
            exit(14)
            
        val1 = self.get_src_value(src1)
        val2 = self.get_src_value(src2)
        
        try:
            if isinstance(val1, str) and val1.isdigit() and isinstance(val2, int):
                val1 = int(val1)
            elif isinstance(val2, str) and val2.isdigit() and isinstance(val1, int):
                val2 = int(val2)
                
            self.log_debug(f"Comparing values: {val1} ({type(val1)}) and {val2} ({type(val2)})")
            
            return comparator(val1, val2)
        except (ValueError, TypeError) as e:
            print(f"Run-time Error: Cannot compare values of different types: {e}", file=sys.stderr)
            exit(14)

    def _jump_common(self, cmd, always_jump=False):
        label = cmd.find('dst')
        if label is None:
            print("Semantic Error: JUMP missing destination.", file=sys.stderr)
            exit(5)
        if label.attrib['kind'] != 'literal' or label.attrib['type'] != 'string' or label.text not in self.labels:
            print("Run-time Error: Invalid jump label.", file=sys.stderr)
            exit(10)
        if always_jump or label.text in self.labels:
            self.pc = self.labels[label.text] - 1 

    def call(self, cmd):
        label = cmd.find('dst')
        if label is None or label.attrib['kind'] != 'literal' or label.attrib['type'] != 'string':
            print("Run-time Error: Invalid call label.", file=sys.stderr)
            exit(14)
        if label.text not in self.labels:
            print("Run-time Error: Function label not found.", file=sys.stderr)
            exit(10)
        self.call_stack.append(self.pc)
        self.pc = self.labels[label.text] - 1

    def return_(self, cmd):
        if not self.call_stack:
            print("Run-time Error: Call stack is empty on RETURN.", file=sys.stderr)
            exit(10)
        self.pc = self.call_stack.pop()
        
    def push(self, cmd):
        src = cmd.find('src1')
        if src is None:
            print("Semantic Error: PUSH missing source argument.", file=sys.stderr)
            exit(5)
        value = self.get_src_value(src)
        self.data_stack.append(value)
        
    def pop(self, cmd):
        dst = cmd.find('dst')
        if dst is None:
            print("Semantic Error: POP missing destination argument.", file=sys.stderr)
            exit(5)
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: POP destination must be a variable.", file=sys.stderr)
            exit(14)
        if not self.data_stack:
            print("Run-time Error: Data stack is empty on POP.", file=sys.stderr)
            exit(10)
        self.variables[dst.text] = self.data_stack.pop()

    def intstr(self, cmd):
        dst, src = cmd.find('dst'), cmd.find('src1')
        if dst is None or src is None:
            print("Semantic Error: INTSTR missing argument.", file=sys.stderr)
            exit(5)
        
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: INTSTR destination must be a variable.", file=sys.stderr)
            exit(14)
            
        val = self.get_src_value(src)
        
        try:
            if not isinstance(val, int):
                val = int(val)
            self.variables[dst.text] = str(val)
        except (ValueError, TypeError) as e:
            print(f"Run-time Error: Cannot convert to string: {e}", file=sys.stderr)
            exit(14)

    def concat(self, cmd):
        dst, src1, src2 = cmd.find('dst'), cmd.find('src1'), cmd.find('src2')
        if None in (dst, src1, src2):
            print("Semantic Error: CONCAT missing argument.", file=sys.stderr)
            exit(5)
        
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: CONCAT destination must be a variable.", file=sys.stderr)
            exit(14)
            
        val1 = self.get_src_value(src1)
        val2 = self.get_src_value(src2)
        
        try:
            str1 = str(val1)
            str2 = str(val2)
            result = str1 + str2
            self.variables[dst.text] = result
            self.log_debug(f"Concatenated: '{str1}' + '{str2}' = '{result}'")
        except Exception as e:
            print(f"Run-time Error: Cannot concatenate: {e}", file=sys.stderr)
            exit(14)

    def len_(self, cmd):
        dst, src = cmd.find('dst'), cmd.find('src1')
        if dst is None or src is None:
            print("Semantic Error: LEN missing argument.", file=sys.stderr)
            exit(5)
        
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: LEN destination must be a variable.", file=sys.stderr)
            exit(14)
            
        val = self.get_src_value(src)
        
        try:
            str_val = str(val)
            length = len(str_val)
            self.variables[dst.text] = length
            self.log_debug(f"String length of '{str_val}': {length}")
        except Exception as e:
            print(f"Run-time Error: Cannot calculate length: {e}", file=sys.stderr)
            exit(14)

    def getat(self, cmd):
        dst, src1, src2 = cmd.find('dst'), cmd.find('src1'), cmd.find('src2')
        if None in (dst, src1, src2):
            print("Semantic Error: GETAT missing argument.", file=sys.stderr)
            exit(5)
        
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: GETAT destination must be a variable.", file=sys.stderr)
            exit(14)
            
        string_val = self.get_src_value(src1)
        index_val = self.get_src_value(src2)
        
        try:
            if not isinstance(index_val, int):
                index_val = int(index_val)
                
            if index_val < 0 or index_val >= len(str(string_val)):
                print(f"Run-time Error: Index {index_val} out of bounds for string of length {len(str(string_val))}", file=sys.stderr)
                exit(10)
                
            result = str(string_val)[index_val]
            self.variables[dst.text] = result
            self.log_debug(f"Character at index {index_val} in '{string_val}': '{result}'")
        except (ValueError, TypeError, IndexError) as e:
            print(f"Run-time Error: Cannot get character at index: {e}", file=sys.stderr)
            exit(14)

    def strbool(self, cmd):
        dst, src = cmd.find('dst'), cmd.find('src1')
        if dst is None or src is None:
            print("Semantic Error: STRBOOL missing argument.", file=sys.stderr)
            exit(5)
        
        if dst.attrib['kind'] != 'variable':
            print("Run-time Error: STRBOOL destination must be a variable.", file=sys.stderr)
            exit(14)
            
        val = self.get_src_value(src)
        
        try:
            if val is True:
                self.variables[dst.text] = "true"
            elif val is False:
                self.variables[dst.text] = "false"
            elif val == 1:
                self.variables[dst.text] = "true"
            elif val == 0:
                self.variables[dst.text] = "false"
            elif isinstance(val, str):
                if val.lower() in ["true", "1"]:
                    self.variables[dst.text] = "true"
                elif val.lower() in ["false", "0"]:
                    self.variables[dst.text] = "false"
                else:
                    self.variables[dst.text] = "false" 
            else:
                self.variables[dst.text] = "true" if val else "false"
                
            self.log_debug(f"Converted boolean '{val}' to string: '{self.variables[dst.text]}'")
        except Exception as e:
            print(f"Run-time Error: Cannot convert to string: {e}", file=sys.stderr)
            exit(14)
