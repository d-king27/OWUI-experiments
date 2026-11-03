"""Strict FDX import: XML text runs are joined without invented spaces."""
import hashlib
import re
from pathlib import Path
from defusedxml import ElementTree
from script_to_voice.contracts import *

MAX_BYTES=8*1024*1024
MAX_ELEMENTS=100000


def parse_fdx(original: bytes, filename: str, *, owner_id: str, project_id: str,
              original_file_id: str) -> ScriptRevision:
    if not filename.lower().endswith('.fdx') or len(original)>MAX_BYTES:
        raise ValueError('Provide an FDX original no larger than 8 MiB')
    try:
        root=ElementTree.fromstring(original,forbid_dtd=True,forbid_entities=True,forbid_external=True)
    except Exception:
        raise ValueError('The file is not valid, safe Final Draft XML') from None
    if root.tag!='FinalDraft' or root.find('Content') is None:
        raise ValueError('Expected a FinalDraft document with Content')
    if sum(1 for _ in root.iter())>MAX_ELEMENTS:
        raise ValueError('Script exceeds the XML element limit')
    source_hash=hashlib.sha256(original).hexdigest()
    revision_id=digest([owner_id,project_id,source_hash])
    def ident(kind, value): return kind+'_'+digest([revision_id,value])[:32]
    paragraphs=list(root.find('Content').iter('Paragraph'))
    scenes=[]; elements=[]; characters={}; warnings=[]
    scene=None; speaker=None; block=None; parentheticals=[]
    for ordinal,p in enumerate(paragraphs):
        kind={'Scene Heading':'scene_heading','Character':'character','Dialogue':'dialogue',
              'Parenthetical':'parenthetical','Action':'action'}.get(p.get('Type'),'unknown')
        runs=tuple(TextRun(text=''.join(t.itertext()),style=t.get('Style','')) for t in p.findall('Text'))
        text=''.join(t.text for t in runs)
        if not text.strip(): continue
        eid=ident('element',ordinal)
        if kind=='scene_heading':
            parts=re.split(r'\s+-\s+',text)
            scene=Scene(id=ident('scene',ordinal),number=p.get('Number',str(len(scenes)+1)),heading=text,
                        location=re.sub(r'^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s*','',parts[0],flags=re.I),
                        time_of_day=parts[-1].strip().upper() if len(parts)>1 else '')
            scenes.append(scene); speaker=None; block=None; parentheticals=[]
        if scene is None:
            scene=Scene(id=ident('scene','preamble'),number='PRE',heading='Unnumbered opening')
            scenes.append(scene)
            warnings.append('Content before the first heading retained in an unnumbered opening scene')
        if kind=='character':
            # Strip only delivery suffixes; role qualifiers such as GUARD (NORTH) retain identity.
            name=re.sub(r"(?:\s*\((?:CONT['’]D\.?|V\.O\.|O\.S\.|OFF|MORE)\))+$",'',text.strip(),flags=re.I).strip().upper()
            speaker='character_'+digest([project_id,name])[:32]
            aliases=set(characters.get(speaker,Character(id=speaker,name=name)).aliases)|{name,text.strip()}
            characters[speaker]=Character(id=speaker,name=name,aliases=tuple(sorted(aliases)))
            block=ident('block',ordinal); parentheticals=[]
        elif kind in ('action','unknown'):
            speaker=None; block=None; parentheticals=[]
        elif kind in ('dialogue','parenthetical') and not speaker:
            raise ValueError(f'Paragraph {ordinal+1} has dialogue or direction without a character')
        attached=tuple(parentheticals) if kind=='dialogue' else ()
        elements.append(ScriptElement(id=eid,scene_id=scene.id,ordinal=ordinal,kind=kind,
            original_text=text,search_text=' '.join(text.casefold().split()),
            character_id=speaker,dialogue_block_id=block,parenthetical_ids=attached,
            source_span=SourceSpan(paragraph=ordinal+1,xpath=f'/FinalDraft/Content//Paragraph[{ordinal+1}]'),runs=runs))
        if kind=='parenthetical': parentheticals.append(eid)
    if not any(e.kind=='dialogue' for e in elements):
        raise ValueError('The FDX contains no attributable dialogue')
    return ScriptRevision(id=revision_id,owner_id=owner_id,project_id=project_id,script_id=project_id,
        original_file_id=original_file_id,original_hash=source_hash,title=Path(filename).stem,
        scenes=tuple(scenes),characters=tuple(characters.values()),elements=tuple(elements),warnings=tuple(warnings))
