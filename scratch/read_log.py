with open("logs/server.log", "r") as f:
    lines = f.readlines()
    for line in lines[-50:]:
        print(line.strip())
