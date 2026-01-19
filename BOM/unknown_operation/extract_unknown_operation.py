import pandas as pd

# Input / output files
input_file = "import.xlsx"
output_file = "output.xlsx"

# Read Excel file
df = pd.read_excel(input_file)

# Ensure we are working with column letters:
# A -> index 0
# B -> index 1
# C -> index 2
# D -> index 3

# Filter rows where B, C, and D are empty
filtered_df = df[
    df.iloc[:, 1].isna() &
    df.iloc[:, 2].isna() &
    df.iloc[:, 3].isna()
]

# Keep only column A
result_df = filtered_df.iloc[:, [0]]

# Write to new Excel file
result_df.to_excel(output_file, index=False, header=False)

print(f"Done. {len(result_df)} rows copied to {output_file}")
