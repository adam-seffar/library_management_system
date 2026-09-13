import pandas as pd

# Load the CSV file
df = pd.read_csv("books_dataset.csv")

cleaned_df = df[
    ~df.isna().any(axis=1) &                   
    ~(df.astype(str).eq("").any(axis=1)) &     
    ~(df.astype(str).eq("[]").any(axis=1))     
]

# Save the cleaned CSV
cleaned_df.to_csv("output.csv", index=False)

print("Cleaned CSV saved as output.csv")