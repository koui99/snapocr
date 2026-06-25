$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$modelDir = Join-Path $root "models\ch-v5"
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

$files = @(
  @{
    Name = "ch_PP-OCRv5_det_mobile.onnx"
    Url  = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.0/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx"
  },
  @{
    Name = "ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx"
    Url  = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.0/onnx/PP-OCRv5/cls/ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx"
  },
  @{
    Name = "ch_PP-OCRv5_rec_mobile.onnx"
    Url  = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.0/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx"
  },
  @{
    Name = "ppocrv5_dict.txt"
    Url  = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.0/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile/ppocrv5_dict.txt"
  }
)

foreach ($file in $files) {
  $dest = Join-Path $modelDir $file.Name
  if (Test-Path $dest) {
    Write-Host "exists $dest"
    continue
  }
  Write-Host "download $($file.Url)"
  Invoke-WebRequest -Uri $file.Url -OutFile $dest
}

Write-Host "Chinese PP-OCRv5 models are ready in: $modelDir"
