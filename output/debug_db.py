import pandas as pd
df = pd.read_csv(r'C:\Users\User\.openclaw\workspace\sj-trading\database\3y_kd\2454_kd.csv')
print(f'Total rows: {len(df)}')
print(f'Columns: {list(df.columns)}')
print(df.tail(10).to_string())
print(f'\nLast K={df["K"].iloc[-1]:.1f} D={df["D"].iloc[-1]:.1f}')
