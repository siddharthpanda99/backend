import os

def fix_imports(root_dir):
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content.replace('common_lib.modules.memory.memory_reasoning', 'common_lib.modules.memory.memory_execution.reasoning')
                
                if content != new_content:
                    print(f"Fixing imports in {path}")
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)

if __name__ == "__main__":
    target = 'c:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo/Python Libs/common_lib/src/common_lib/modules/memory/memory_execution/reasoning'
    fix_imports(target)
