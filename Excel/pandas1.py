from cmath import nan
from encodings import utf_8
import pandas as pd
from openpyxl import load_workbook
from sympy import true

workbook = pd.read_excel(r'C:\Users\Rajo\Develop\Excel\primer_ponuda.xls')
df1 = pd.read_excel(r'C:\Users\Rajo\Develop\Excel\primer_ponuda.xls', sheet_name=1) #dataframe
print(df1)

l=[]
sablon = "OPIS RADOVA"

for row in range(0, 6):
    for column in range(0, 6):
        val = str(df1.iat[row, column])
        if "OPIS RADOVA" in val:
            print(val)
            hederRow = row
            print(row)
            print(column)


for column in range(0,6):
    heder = str(df1.iat[hederRow, column])
    l.append(heder)

print(l)

total_rows = len(df1)
print(total_rows)

redni_br =[]
for row in range(3,115):
    value = df1.iat[row, 0]
    if df1[row, 0].empty == True:
        pass
    else:
        redni_br.append(df1[row, 0])

print(redni_br)
