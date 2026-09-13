with open("main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
patched_init = False
patched_dict = False

for line in lines:
    # Match the news query comment dynamically regardless of leading spaces
    if "Query ca.document_vector_chunks for Segment 4 Houseviews & News" in line and not patched_init:
        indent = line[:line.find("#")]
        new_lines.append(f'{indent}houseview_label = "Debt Maturity Wall: €10.13bn"\n')
        patched_init = True
    
    new_lines.append(line)
    
    # Inject houseview_label right after news_headline dictionary key
    if '"news_headline": news_headline,' in line and not patched_dict:
        dict_indent = line[:line.find('"news_headline"')]
        new_lines.append(f'{dict_indent}"houseview_label": houseview_label,\n')
        patched_dict = True

if patched_init and patched_dict:
    with open("main.py", "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("✓ Successfully patched main.py dynamically.")
else:
    print(f"✗ Patch failed. Initialized: {patched_init}, Dict serialized: {patched_dict}")
