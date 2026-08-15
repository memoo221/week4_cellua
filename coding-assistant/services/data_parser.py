



import io

import pandas as pd
from fastapi import UploadFile


def parse_csv_to_dataframe(file: UploadFile) -> pd.DataFrame:
   return pd.read_csv(io.BytesIO(file), encoding="utf-8")   

   