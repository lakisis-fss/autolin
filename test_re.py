import re
data = open('rsc_detail.txt', encoding='utf-8').read()
idx = data.find('"npcid"')
print(data[max(0, idx-50):idx+500])
