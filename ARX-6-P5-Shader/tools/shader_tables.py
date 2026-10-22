"""Exact desktop transport for numeric arrays already embedded in the GLSL.

The portable shader keeps all constants. This optional OpenGL 4.3 path moves
their identical float32/int32 values to one read-only std430 storage buffer.
It changes neither the procedural geometry nor the fragment ray evaluator,
and uses no meshes or textures. Avoiding enormous compiler constant selectors
reduces software-driver startup and indexed-table access costs.
"""
import hashlib,re
import numpy as np

ARRAY=re.compile(r'const\s+(vec[234]|ivec[234]|float|int)\s+(\w+)\[(\d+)\]\s*=\s*\1\[\d*\]\s*\((.*?)\);',re.S)
NUMBER=re.compile(r'(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')

def convert(source):
 chunks=[];metadata=[];declarations=[];length=0
 def table(m):
  nonlocal length
  typ,name,count,body=m.groups();count=int(count)
  if not name.startswith(('CSG_','BVH_','POLY_BVH_','SPRING_','P5_FINISH')):return m.group(0)
  width=int(typ[-1]) if 'vec' in typ else 1
  integer=typ.startswith('ivec') or typ=='int'
  clean=re.sub(r'\b(?:i?vec[234])\s*\(','(',body)
  values=NUMBER.findall(clean)
  residue=NUMBER.sub('',clean)
  if re.sub(r'[\s(),]','',residue):raise ValueError('Nonliteral table expression in '+name)
  if len(values)!=count*width:raise ValueError(f'{name}: expected {count*width} scalars, got {len(values)}')
  alignment=4 if width==1 else 8 if width==2 else 16
  stride=4 if width==1 else 8 if width==2 else 16
  padding=(-length)%alignment
  chunks.append(bytes(padding));length+=padding;offset=length
  dtype=np.dtype('<i4' if integer else '<f4')
  if integer:
   numbers=np.asarray([int(x) for x in values],dtype=dtype)
  else:numbers=np.asarray([float(x) for x in values],dtype=dtype)
  packed=np.zeros((count,stride//4),dtype=dtype);packed[:,:width]=numbers.reshape(count,width)
  raw=packed.tobytes();chunks.append(raw);length+=len(raw)
  metadata.append({'name':name,'type':typ,'count':count,'offset':offset,'stride':stride,'bytes':len(raw),'value_sha256':hashlib.sha256(numbers.tobytes()).hexdigest()})
  declarations.append(f'    {typ} {name}[{count}];')
  return '__ARX_TABLE_BLOCK__' if len(metadata)==1 else '// '+name+' is in the immutable numeric table buffer.'
 transformed=ARRAY.sub(table,source)
 if not metadata:raise ValueError('No supported procedural geometry tables found')
 block='layout(std430, binding=0) readonly buffer ARXNumericGeometry {\n'+'\n'.join(declarations)+'\n};'
 transformed=transformed.replace('__ARX_TABLE_BLOCK__',block)
 # The block itself has the maximum member alignment (16 bytes here),
 # including trailing padding required by GL_BUFFER_DATA_SIZE.
 tail_padding=(-length)%16
 chunks.append(bytes(tail_padding))
 raw=b''.join(chunks)
 return transformed,raw,{'tables':metadata,'table_count':len(metadata),'bytes':len(raw),'tail_padding_bytes':tail_padding,'sha256':hashlib.sha256(raw).hexdigest(),'transport':'Exact literal float32/int32 arrays in one read-only std430 SSBO; no meshes, no geometry or material textures.'}
