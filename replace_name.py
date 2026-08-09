import os

replacements = [
    ("Business Management System", "Business Management System"),
    ("Business Management", "Business Management"),
    ("BUSINESS SYSTEM", "BUSINESS SYSTEM"),
    ("Business System", "Business System"),
    ("business", "business"),
]

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('e:/personal/shop'):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py') or file.endswith('.html') or file.endswith('.md'):
            process_file(os.path.join(root, file))

print("Replacement complete.")
