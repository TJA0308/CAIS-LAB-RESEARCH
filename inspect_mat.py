from scipy.io import loadmat
from pathlib import Path

from config import MAT_FILE

mat_path = Path(MAT_FILE)

if not mat_path.exists():
    raise FileNotFoundError(f"Could not find MAT file: {MAT_FILE}")

mat = loadmat(MAT_FILE, squeeze_me=True, struct_as_record=False)

print(f"Inspecting MAT file: {MAT_FILE}")
print("\nVariables inside MAT file:")

for key, value in mat.items():
    if key.startswith("__"):
        continue

    print(f"- {key}: type={type(value)}, shape={getattr(value, 'shape', 'no shape')}")

    # If this is a MATLAB struct, print its fields
    if hasattr(value, "_fieldnames"):
        print(f"  Fields inside {key}:")

        for field in value._fieldnames:
            field_value = getattr(value, field)

            if hasattr(field_value, "shape"):
                shape = field_value.shape
            else:
                shape = "scalar/no shape"

            print(f"  - {field}: type={type(field_value)}, shape={shape}")

            # Print useful metadata values directly
            if field in ["startWallClock", "endWallClock", "durationSeconds", "timestampMeaning", "source"]:
                print(f"    value: {field_value}")