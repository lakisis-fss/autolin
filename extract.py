import json

def extract_monsters(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        data = f.read()

    monsters = []
    idx = 0
    search_str = '{"monster":{'
    
    while True:
        idx = data.find(search_str, idx)
        if idx == -1:
            break
        
        # Found a monster object, it starts at idx + 11 (the second '{')
        # We need to extract the whole {"npcid":...} object
        start = idx + 11
        end = start
        brace_count = 0
        
        for i in range(start, len(data)):
            if data[i] == '{':
                brace_count += 1
            elif data[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        obj_str = data[start:end]
        try:
            monster = json.loads(obj_str)
            monsters.append(monster)
        except json.JSONDecodeError as e:
            # Maybe the string contains RSC escape codes or JS? Let's just catch and ignore or print
            print(f"Decode error at {start}-{end}: {e}")
            pass
        
        idx = end

    return monsters

res = extract_monsters('rsc_data.txt')
print(f"Extracted {len(res)} monsters!")
if res:
    print(json.dumps(res[0], ensure_ascii=False, indent=2))
