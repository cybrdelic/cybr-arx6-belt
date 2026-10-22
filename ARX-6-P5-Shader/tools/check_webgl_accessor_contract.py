"""CPU proof of generated UBO accessors against literal GLSL; no GPU claim."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import re

import numpy as np
import webgl_tables

ROOT = Path(__file__).resolve().parents[1]
ARRAY = re.compile(r'const\s+(vec[234]|ivec[234]|float|int)\s+(\w+)\[(\d+)\]\s*=\s*\1\[\d*\]\s*\((.*?)\);', re.S)
NUMBER = re.compile(r'(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
PREFIXES = ('CSG_', 'BVH_', 'POLY_BVH_', 'SPRING_', 'P5_FINISH')
EXPECTED_DATA = {
    65536: '714797b47f6e7718ca1c9798a240ceb3bdcc41cef2dcd11f0bb9ab751990c10b',
    32768: '714797b47f6e7718ca1c9798a240ceb3bdcc41cef2dcd11f0bb9ab751990c10b',
    16384: '0f96c83ca57b49e75ffa407c1bb709e8126c3a14e0d508809b00990970aab8d2',
}


def integer_expression(expression, index):
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name) and node.id == 'i':
            return index
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.RShift):
                return a >> b
        raise AssertionError('Unexpected accessor expression: ' + ast.dump(node))
    return walk(ast.parse(expression, mode='eval'))


def verify():
    source = (ROOT / 'ARX-6-P5-Live.glsl').read_text(encoding='utf-8')
    reference = {}
    for match in ARRAY.finditer(source):
        typ, name, count, body = match.groups()
        if not name.startswith(PREFIXES):
            continue
        count = int(count)
        width = int(typ[-1]) if 'vec' in typ else 1
        clean = re.sub(r'\b(?:i?vec[234])\s*\(', '(', body)
        values = NUMBER.findall(clean)
        assert not re.sub(r'[\s(),]', '', NUMBER.sub('', clean)), name
        assert len(values) == count * width, name
        integer = typ.startswith('ivec') or typ == 'int'
        numbers = np.array([int(v) if integer else float(v) for v in values], dtype='<i4' if integer else '<f4')
        assert np.isfinite(numbers).all(), name
        reference[name] = (typ, count, width, numbers.view('<u4').reshape(count, width), match.group(0))
    assert len(reference) == 36
    results = []
    for variant in webgl_tables.build(source)['variants']:
        size = variant['maximum_block_bytes']
        raw_blocks = [base64.b64decode(block['base64']) for block in variant['blocks']]
        actual_hash = hashlib.sha256(b''.join(raw_blocks)).hexdigest()
        assert actual_hash == EXPECTED_DATA[size] == variant['data_sha256']
        blocks = [np.frombuffer(raw, dtype='<u4').reshape(-1, 4) for raw in raw_blocks]
        selected = set()
        scalar_checks = element_checks = crossing = 0
        for row in variant['tables']:
            name = row['name']
            selected.add(name)
            typ, count, width, expected_bits, declaration = reference[name]
            matches = list(re.finditer(r'\b' + re.escape(typ) + r' ARX_' + re.escape(name) + r'\(int i\) \{ ([^{}]*)\}', variant['source']))
            assert len(matches) == 1, name
            body = matches[0].group(1)
            direct = re.search(r'uvec4 words=arxData(\d+)\[([^\]]+)\];', body)
            conditions = []
            if not direct:
                crossing += 1
                expression = re.search(r'int wordIndex=([^;]+);', body).group(1)
                conditions = [tuple(map(int, x)) for x in re.findall(r'(?:else )?if\(wordIndex<(\d+)\) words=arxData(\d+)\[wordIndex-(\d+)\];', body)]
                final = tuple(map(int, re.search(r'else words=arxData(\d+)\[wordIndex-(\d+)\];', body).groups()))
            integer = typ.startswith('ivec') or typ == 'int'
            if width >= 3:
                value = 'words.xyz' if width == 3 else 'words'
                expected_return = f'{typ}({value})' if integer else f'uintBitsToFloat({value})'
            elif width == 2:
                assert 'uvec2 value=(i&1)==0?words.xy:words.zw;' in body
                expected_return = 'ivec2(value)' if integer else 'uintBitsToFloat(value)'
            else:
                expected_return = 'int(words[i&3])' if integer else 'uintBitsToFloat(words[i&3])'
            assert body[body.index('return '):] == 'return ' + expected_return + '; ', name
            for index in range(count):
                if direct:
                    block = int(direct.group(1))
                    word = integer_expression(direct.group(2), index)
                else:
                    absolute = integer_expression(expression, index)
                    block, offset = final
                    for bound, choice, start in conditions:
                        if absolute < bound:
                            block, offset = choice, start
                            break
                    word = absolute - offset
                assert 0 <= block < len(blocks) and 0 <= word < len(blocks[block]), (name, index, block, word)
                lanes = list(range(width)) if width >= 3 else [2 * (index % 2), 2 * (index % 2) + 1] if width == 2 else [index % 4]
                assert np.array_equal(blocks[block][word, lanes], expected_bits[index]), (name, index)
                scalar_checks += width
                element_checks += 1
        for name, (typ, count, width, bits, declaration) in reference.items():
            if name not in selected:
                assert declaration in variant['source'], name
                scalar_checks += count * width
        assert scalar_checks == 55342
        results.append(dict(block_bytes=size, blocks=len(blocks), transported_tables=len(selected), crossing_tables=crossing, scalar_checks=scalar_checks, transported_element_checks=element_checks, unchanged_literal_tables=len(reference)-len(selected), data_sha256=actual_hash))
    return dict(passed=True, gpu_execution=False, original_normalized_text_sha256=hashlib.sha256(source.encode()).hexdigest(), total_scalar_checks=sum(r['scalar_checks'] for r in results), variants=results)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
