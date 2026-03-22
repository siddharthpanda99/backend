try:
    print("TESTING SELECTIVE IMPORT OF MIDAS...")
    from controlnet_aux.midas import MidasDetector
    print("SUCCESS: Selective Midas import works!")
except Exception as e:
    print(f"FAILED: Selective Midas import failed: {e}")

try:
    print("TESTING SELECTIVE IMPORT OF OPENPOSE...")
    from controlnet_aux.open_pose import OpenposeDetector
    print("SUCCESS: Selective OpenPose import works!")
except Exception as e:
    print(f"FAILED: Selective OpenPose import failed: {e}")
