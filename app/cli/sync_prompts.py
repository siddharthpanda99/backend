import os
import sqlite3
import ijson
import traceback

def get_db_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return os.path.join(base_dir, "resources", "prompts.db")

chats_dir = os.path.expanduser(r"~/.config/manicode/projects/Monorepo/chats")

def main():
    db_path = get_db_path()
    print(f"Connecting to DB: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    inserted_count = 0
    errors = 0
    skipped_folders = 0
    
    if not os.path.exists(chats_dir):
        print(f"Chats directory not found at {chats_dir}")
        return
        
    for folder_name in os.listdir(chats_dir):
        folder_path = os.path.join(chats_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
            
        chat_file = os.path.join(folder_path, "chat-messages.json")
        if not os.path.exists(chat_file):
            continue
            
        # Get current file size
        file_size = os.path.getsize(chat_file)
        
        # Check last sync state
        c.execute("SELECT file_size FROM sync_state WHERE folder_name = ?", (folder_name,))
        row = c.fetchone()
        if row and row[0] == file_size:
            skipped_folders += 1
            continue
            
        try:
            date_str = folder_name.split('T')[0]
        except:
            date_str = folder_name
            
        print(f"Syncing new or updated folder: {folder_name} (Size: {file_size} bytes)")
        
        try:
            with open(chat_file, 'rb') as f:
                for msg in ijson.items(f, 'item'):
                    if isinstance(msg, dict) and msg.get('variant') == 'user':
                        message_id = msg.get('id', '')
                        text = ""
                        
                        blocks = msg.get('blocks', [])
                        if blocks and isinstance(blocks, list):
                            text_parts = []
                            for block in blocks:
                                if isinstance(block, dict) and block.get('type') == 'text':
                                    text_parts.append(block.get('content', ''))
                            text = "\n".join(text_parts).strip()
                        elif isinstance(msg.get('content'), str):
                            text = msg.get('content').strip()
                            
                        if text:
                            # Check if message_id exists
                            c.execute("SELECT id FROM prompts WHERE message_id = ?", (message_id,))
                            if c.fetchone():
                                continue
                                
                            # Check if we have an existing prompt without message_id (backfill)
                            c.execute("SELECT id FROM prompts WHERE prompt = ? AND message_id IS NULL", (text,))
                            existing = c.fetchone()
                            
                            if existing:
                                # Update existing record with message_id
                                c.execute("UPDATE prompts SET message_id = ? WHERE id = ?", (message_id, existing[0]))
                            else:
                                # Insert new
                                c.execute(
                                    "INSERT INTO prompts (prompt, processed, date, message_id) VALUES (?, ?, ?, ?)",
                                    (text, 0, date_str, message_id)
                                )
                                inserted_count += 1
                                
            # Update sync state
            c.execute("INSERT OR REPLACE INTO sync_state (folder_name, file_size) VALUES (?, ?)", (folder_name, file_size))
            conn.commit()
            
        except Exception as e:
            errors += 1
            print(f"Failed to process {folder_name}: {str(e)}")
            
    conn.commit()
    conn.close()
    print(f"\nSync complete!")
    print(f"Inserted: {inserted_count}")
    print(f"Skipped unmodified folders: {skipped_folders}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
