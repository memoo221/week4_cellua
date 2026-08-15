'''
haya5od el datset form the user w y3mllo save f el database

'''
from services.data_parser import parse_csv_to_dataframe
from services.dataset_store import save_dataset, initialize_database
from fastapi import APIRouter, UploadFile, File, Form
router = APIRouter()
@router.post("/upload_dataset")
async def upload_dataset(file: UploadFile = File(...)):
    df = parse_csv_to_dataframe(await file.read())
    save_dataset(df, file.filename)
    return {"message": "Dataset uploaded and saved successfully.", "columns": list(df.columns)}