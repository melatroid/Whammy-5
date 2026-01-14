try:
    import app
except Exception as e:
    try:
        print("[BOOT] Failed to import NEO:", e)
    except:
        pass
    raise
