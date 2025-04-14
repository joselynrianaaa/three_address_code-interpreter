import sys
import xml.etree.ElementTree as ET
from interpreter import Interpreter

def infer_type(value):
    if value is None:
        return "variable"
    if value.isdigit():
        return "integer"
    if value.startswith('"') and value.endswith('"'):
        return "string"
    if value in ["True", "False", "true", "false"]:
        return "string"  
    if all(c.isalnum() or c == '_' for c in value):  
        return "variable"
    if " " in value:
        return "string"
    return "variable" 

def optimize_tac_xml(input_file, output_file):
    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
    except Exception as e:
        print(f"[❌] Failed to parse XML: {e}")
        return

    instructions = []
    live_vars = set()
    constant_table = {}
    copy_table = {}
    labels_used = set() 

    for instr in root.iter('taci'):
        op = instr.attrib.get('opcode').upper()
        arg1_elem = instr.find('src1')
        arg2_elem = instr.find('src2')
        result_elem = instr.find('dst')

        arg1 = arg1_elem.text.strip() if arg1_elem is not None and arg1_elem.text else None
        arg2 = arg2_elem.text.strip() if arg2_elem is not None and arg2_elem.text else None
        result = result_elem.text.strip() if result_elem is not None and result_elem.text else None

        instructions.append((op, arg1, arg2, result))

        if op in ['PRINT', 'IFGOTO', 'JUMPIFEQ']:
            if arg1: live_vars.add(arg1)
            if arg2: live_vars.add(arg2)
        else:
            if arg1 and not arg1.isdigit(): live_vars.add(arg1)
            if arg2 and not arg2.isdigit(): live_vars.add(arg2)
            
        if op in ['JUMP', 'JUMPIFEQ', 'JUMPIFGR', 'CALL', 'IFGOTO'] and result:
            labels_used.add(result)

    print(f"[🔍] Parsed {len(instructions)} instructions from XML")

    optimized_instructions = []
    for op, arg1, arg2, result in instructions:
        if op in ['ADD', 'SUB', 'MUL', 'DIV']:
            if arg1 and arg1.isdigit() and arg2 and arg2.isdigit():
                calc = str(eval(f"{arg1} {op.lower()} {arg2}"))
                optimized_instructions.append(('MOV', calc, None, result))
                constant_table[result] = calc
                print(f"[🔧] Constant folded: {arg1} {op} {arg2} => {calc}")
            else:
                optimized_instructions.append((op, arg1, arg2, result))
        elif op == 'MOV' or op == '=':
            if arg1 in constant_table:
                optimized_instructions.append(('MOV', constant_table[arg1], None, result))
                print(f"[🔁] Propagated constant: {result} = {constant_table[arg1]}")
            elif arg1 and arg1.isdigit():
                constant_table[result] = arg1
                optimized_instructions.append((op, arg1, None, result))
            else:
                copy_table[result] = arg1
                optimized_instructions.append((op, arg1, None, result))
        elif op == 'PRINT':
            if arg1 in copy_table:
                arg1 = copy_table[arg1]
            optimized_instructions.append((op, arg1, None, None))
        elif op == 'LABEL':
            if result in labels_used:
                optimized_instructions.append((op, None, None, result))
            else:
                print(f"[🧹] Removed unused label: {result}")
        else:
            optimized_instructions.append((op, arg1, arg2, result))

    final_instructions = []
    for op, arg1, arg2, result in optimized_instructions:
        always_keep = ['PRINT', 'IFGOTO', 'JUMPIFEQ', 'JUMPIFGR', 'JUMP', 'LABEL', 'CALL', 'RETURN']
        
        if result and result not in live_vars and op not in always_keep:
            print(f"[🧹] Removed dead code: {op} {arg1} {arg2} -> {result}")
            continue
        final_instructions.append((op, arg1, arg2, result))

    existing_labels = {instr[3] for instr in final_instructions if instr[0] == 'LABEL'}
    for label in labels_used:
        if label not in existing_labels:
            print(f"[➕] Adding missing label: {label}")
            final_instructions.append(('LABEL', None, None, label))

    if not final_instructions:
        print("[⚠️] No instructions left after optimization. Output may be empty.")

    opt_root = ET.Element("program", name="Optimized")
    for op, arg1, arg2, result in final_instructions:
        instr = ET.SubElement(opt_root, "taci", opcode=op)

        if op == 'PRINT':
            if arg1:
                src1 = ET.SubElement(instr, "src1")
                if arg1 in ["True", "False", "true", "false"]:
                    src1.set("type", "string")
                    src1.set("kind", "literal")
                else:
                    src1.set("type", infer_type(arg1))
                    src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1
        elif op == 'READINT':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "integer")
                dst.set("kind", "variable")
                dst.text = result
        elif op == 'READSTR':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "string")
                dst.set("kind", "variable")
                dst.text = result
        elif op == 'INTSTR':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "string")
                dst.set("kind", "variable")
                dst.text = result
            if arg1:
                src1 = ET.SubElement(instr, "src1")
                src1.set("type", "integer") 
                src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1
        elif op == 'CONCAT':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "string")
                dst.set("kind", "variable")
                dst.text = result
            if arg1:
                src1 = ET.SubElement(instr, "src1")
                src1.set("type", "string")  
                src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1
            if arg2:
                src2 = ET.SubElement(instr, "src2")
                src2.set("type", "string") 
                src2.set("kind", "variable" if infer_type(arg2) == "variable" else "literal")
                src2.text = arg2
        elif op == 'LEN':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "integer") 
                dst.set("kind", "variable")
                dst.text = result
            if arg1:
                src1 = ET.SubElement(instr, "src1")
                src1.set("type", "string") 
                src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1
        elif op == 'GETAT':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "string") 
                dst.set("kind", "variable")
                dst.text = result
            if arg1:
                src1 = ET.SubElement(instr, "src1")
                src1.set("type", "string") 
                src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1
            if arg2:
                src2 = ET.SubElement(instr, "src2")
                src2.set("type", "integer") 
                src2.set("kind", "variable" if infer_type(arg2) == "variable" else "literal")
                src2.text = arg2
        elif op == 'STRBOOL':
            if result:
                dst = ET.SubElement(instr, "dst")
                dst.set("type", "string") 
                dst.set("kind", "variable")
                dst.text = result
            if arg1:
                src1 = ET.SubElement(instr, "src1")
                src1.set("type", infer_type(arg1)) 
                src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1
        else:
            if result:
                dst = ET.SubElement(instr, "dst")
                if op == 'LABEL' or op in ['JUMP', 'JUMPIFEQ', 'JUMPIFGR', 'CALL', 'IFGOTO']:
                    dst.set("type", "string")
                    dst.set("kind", "literal")
                else:
                    dst.set("type", infer_type(result))
                    dst.set("kind", "variable" if infer_type(result) == "variable" else "literal")
                dst.text = result

            if arg1:
                src1 = ET.SubElement(instr, "src1")
                src1.set("type", infer_type(arg1))
                src1.set("kind", "variable" if infer_type(arg1) == "variable" else "literal")
                src1.text = arg1

            if arg2:
                src2 = ET.SubElement(instr, "src2")
                src2.set("type", infer_type(arg2))
                src2.set("kind", "variable" if infer_type(arg2) == "variable" else "literal")
                src2.text = arg2

    tree = ET.ElementTree(opt_root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"[✅] Optimized XML written to {output_file} ({len(final_instructions)} instructions)")

def main():
    if len(sys.argv) < 2:
        print('Usage:\n  python tacy.py <file.xml>             # Just interpret\n  python tacy.py --opt <file.xml>        # Optimize and interpret\n  python tacy.py --benchmark <file.xml>  # Compare original vs optimized performance')
        exit(1)

    debug_mode = False
    
    if sys.argv[1] == '--benchmark':
        if len(sys.argv) < 3:
            print("[❌] Missing input XML file for benchmarking.")
            exit(1)
        input_file = sys.argv[2]
        output_file = input_file.replace(".xml", "_optimized.xml")
        
        # Optimize the code
        print("[🔧] Optimizing XML code...")
        optimize_tac_xml(input_file, output_file)
        
        # Run original code
        print("\n[⏱️] Running original code...")
        original_app = Interpreter(input_file, debug_mode)
        original_time = original_app.run()
        
        # Run optimized code
        print("\n[⏱️] Running optimized code...")
        optimized_app = Interpreter(output_file, debug_mode)
        optimized_time = optimized_app.run()
        
        # Show timing comparison
        print("\n[📊] PERFORMANCE COMPARISON:")
        print(f"Original code execution time:  {original_time:.6f} seconds")
        print(f"Optimized code execution time: {optimized_time:.6f} seconds")
        
        if original_time > 0:
            improvement = ((original_time - optimized_time) / original_time) * 100
            print(f"Performance improvement:      {improvement:.2f}%")
        else:
            print("Performance improvement:      N/A (original execution time too small)")
    
    elif sys.argv[1] == '--opt':
        if len(sys.argv) < 3:
            print("[❌] Missing input XML file for optimization.")
            exit(1)
        input_file = sys.argv[2]
        output_file = input_file.replace(".xml", "_optimized.xml")
        optimize_tac_xml(input_file, output_file)
        debug_mode = False
        app = Interpreter(output_file, debug_mode)
        app.run()
    else:
        input_file = sys.argv[1]
        app = Interpreter(input_file, debug_mode)
        app.run()

if __name__ == '__main__':
    main()
