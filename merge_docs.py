import os

docs_dir = 'docs'
output_file = 'architecture.md'

files_to_merge = [
    '1_overview.md',
    '2_services.md',
    '3_ml.md',
    '4_data.md',
    '5_gui.md'
]

with open(output_file, 'w', encoding='utf-8') as outfile:
    for filename in files_to_merge:
        filepath = os.path.join(docs_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read())
                outfile.write('\n\n---\n\n')

print('architecture.md successfully created!')
