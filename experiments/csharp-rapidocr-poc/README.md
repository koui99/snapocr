# C# RapidOCR PoC

Purpose: quickly evaluate a C# OCR stack before rewriting SnapOCR.

This PoC uses [`RapidOcrNet`](https://www.nuget.org/packages/RapidOcrNet/) 2.0.0:

- PaddleOCR/RapidOCR pipeline on ONNX Runtime
- no OpenCV dependency
- net8.0 compatible
- bundled PP-OCRv5 **latin** defaults
- supports custom Chinese PP-OCRv5 ONNX models via CLI paths

## Prerequisites

- Windows 10/11 or Linux/macOS with .NET SDK 8+
- For final SnapOCR migration, Windows is the target platform

## Quick English/Latin smoke test

```powershell
cd experiments/csharp-rapidocr-poc
dotnet restore
dotnet run -- path\to\image.png --draw out.png --json out.json
```

The default bundled model is latin. It is useful for checking package/runtime behavior,
but not enough for Chinese screenshots.

## Chinese OCR test

Download Chinese PP-OCRv5 mobile models:

```powershell
cd experiments/csharp-rapidocr-poc
powershell -ExecutionPolicy Bypass -File .\scripts\download-chinese-v5.ps1
```

Run with explicit model paths:

```powershell
dotnet run -- path\to\image.png `
  --det .\models\ch-v5\ch_PP-OCRv5_det_mobile.onnx `
  --cls .\models\ch-v5\ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx `
  --rec .\models\ch-v5\ch_PP-OCRv5_rec_mobile.onnx `
  --keys .\models\ch-v5\ppocrv5_dict.txt `
  --draw out.png --json out.json
```

Model sizes from ModelScope listing:

- det: ~4.8 MB
- cls: ~1.0 MB
- rec: ~16.6 MB
- dict: ~74 KB

## Publish size checks

Framework-dependent Windows build, smaller but requires .NET 8 runtime installed:

```powershell
dotnet publish -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -o publish\win-x64-fd
```

Self-contained Windows build, larger but double-click ready:

```powershell
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o publish\win-x64-sc
```

## What to compare against Python SnapOCR

Use the same screenshots and compare:

1. Chinese UI text
2. English text
3. small text
4. dark background text
5. mixed Chinese/English
6. speed and first-run model load time
7. published folder size

If OCR quality and size are acceptable, the next step is a C# WPF SnapOCR shell PoC:

- tray icon
- RegisterHotKey
- screenshot overlay
- pinned image window
- WPF Canvas annotations
