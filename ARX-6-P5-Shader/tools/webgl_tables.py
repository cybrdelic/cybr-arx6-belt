"""Exact WebGL 2 transport for the shader's literal numerical CAD tables.

The shader still evaluates all geometry and shading. This changes only how
immutable numeric constants reach it, using standard uniform buffers, with
no triangle meshes, geometry textures, or material textures. The downloadable
standalone GLSL retains its self-contained literal arrays.
"""
import base64,hashlib,re
import numpy as np
from shader_tables import ARRAY,NUMBER

PREFIXES=('CSG_','BVH_','POLY_BVH_','SPRING_','P5_FINISH')

def tables(source):
    result=[]
    for m in ARRAY.finditer(source):
        typ,name,count,body=m.groups();count=int(count)
        if not name.startswith(PREFIXES):continue
        width=int(typ[-1]) if 'vec' in typ else 1
        integer=typ.startswith('ivec') or typ=='int'
        clean=re.sub(r'\b(?:i?vec[234])\s*\(','(',body)
        scalars=NUMBER.findall(clean)
        if re.sub(r'[\s(),]','',NUMBER.sub('',clean)):
            raise ValueError('Nonliteral table '+name)
        if len(scalars)!=count*width:raise ValueError('Wrong scalar count '+name)
        values=np.asarray([int(v) if integer else float(v) for v in scalars],dtype='<i4' if integer else '<f4')
        stride=4 if width==3 else width
        packed=np.zeros((count,stride),dtype='<u4')
        packed[:,:width]=values.view('<u4').reshape(count,width)
        raw=packed.tobytes();raw+=bytes((-len(raw))%16)
        result.append({'name':name,'type':typ,'width':width,'count':count,'raw':raw,'bytes':len(raw),'value_sha256':hashlib.sha256(values.tobytes()).hexdigest()})
    return result

def replace_indexing(source,names):
    pattern=re.compile(r'\b('+'|'.join(sorted(names,key=len,reverse=True))+r')\s*\[')
    output=[];cursor=0
    while True:
        match=pattern.search(source,cursor)
        if match is None:
            output.append(source[cursor:]);break
        end=match.end();depth=1
        while end<len(source) and depth:
            if source[end]=='[':depth+=1
            elif source[end]==']':depth-=1
            end+=1
        if depth:raise ValueError('Unclosed table index '+match.group(1))
        expression=replace_indexing(source[match.end():end-1],names)
        output.extend([source[cursor:match.start()],'ARX_'+match.group(1)+'('+expression+')'])
        cursor=end
    return ''.join(output)

def variant(source,all_tables,block_bytes,max_blocks=12):
    budget=block_bytes*max_blocks
    # Keep the longest dynamic arrays out of compiler-generated literal selectors.
    selected=set();used=0
    for table in sorted(all_tables,key=lambda x:(-x['count'],-x['bytes'])):
        if used+table['bytes']<=budget:
            selected.add(table['name']);used+=table['bytes']
    chunks=[];rows=[];offset=0
    for table in all_tables:
        if table['name'] not in selected:continue
        row={k:v for k,v in table.items() if k!='raw'}
        row['offset_bytes']=offset;rows.append(row)
        chunks.append(table['raw']);offset+=len(table['raw'])
    raw=b''.join(chunks)
    blocks=[raw[i:i+block_bytes] for i in range(0,len(raw),block_bytes)]
    declarations=[];branches=[];block_meta=[]
    for i,data in enumerate(blocks):
        count=len(data)//16;base=i*block_bytes//16
        declarations.append(f'layout(std140) uniform ARXNumericBlock{i} {{ highp uvec4 arxData{i}[{count}]; }};')
        branches.append(f'    if(i<{base+count}) return arxData{i}[i-{base}];')
        block_meta.append({'name':f'ARXNumericBlock{i}','binding':i,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'base64':base64.b64encode(data).decode()})
    helper='\n'.join(declarations)+'\nhighp uvec4 ARXTableWords(int i) {\n'+'\n'.join(branches)+'\n    return uvec4(0);\n}\n'
    functions=[]
    for row in rows:
        w=row['width'];typ=row['type'];base=row['offset_bytes']//16
        index=f'{base}+i' if w>=3 else f'{base}+(i>>{1 if w==2 else 2})'
        body=f'uvec4 words=ARXTableWords({index}); '
        if w>=3:
            words='words.xyz' if w==3 else 'words'
            expression=f'{typ}({words})' if typ.startswith('ivec') else f'uintBitsToFloat({words})'
        elif w==2:
            body+='uvec2 value=(i&1)==0?words.xy:words.zw; '
            expression='ivec2(value)' if typ.startswith('ivec') else 'uintBitsToFloat(value)'
        else:
            expression='int(words[i&3])' if typ=='int' else 'uintBitsToFloat(words[i&3])'
        functions.append(f'{typ} ARX_{row["name"]}(int i) {{ {body}return {expression}; }}')
    stripped=ARRAY.sub(lambda m:'// '+m.group(2)+' is supplied as immutable literal bits.' if m.group(2) in selected else m.group(0),source)
    for row in rows:
        stripped=re.sub(r'\b'+re.escape(row['name'])+r'\s*\.\s*length\s*\(\s*\)',str(row['count']),stripped)
    transformed=helper+'\n'+'\n'.join(functions)+'\n'+replace_indexing(stripped,selected)
    return {'maximum_block_bytes':block_bytes,'block_count':len(blocks),'table_count':len(rows),'table_bytes':len(raw),'literal_tables_remaining':len(all_tables)-len(rows),'source':transformed,'shader_sha256':hashlib.sha256(transformed.encode()).hexdigest(),'literal_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'data_sha256':hashlib.sha256(raw).hexdigest(),'tables':rows,'blocks':block_meta}

def build(source):
    all_tables=tables(source)
    return {'method':'Exact float32/int32 literal bit patterns in standard WebGL2 uniform buffers. Geometry and materials remain evaluated by the fragment shader. No meshes or geometry/material textures.','variants':[variant(source,all_tables,n) for n in (65536,32768,16384)]}
