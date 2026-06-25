using System.Diagnostics;
using System.Text.Json;
using RapidOcrNet;
using SkiaSharp;

var cli = CliOptions.Parse(args);
if (cli is null)
{
    CliOptions.PrintUsage();
    return 2;
}

if (!File.Exists(cli.ImagePath))
{
    Console.Error.WriteLine($"Image not found: {cli.ImagePath}");
    return 2;
}

var modelMode = cli.HasCustomModels ? "custom" : "bundled-latin";
Console.Error.WriteLine($"C# RapidOCR PoC: image={cli.ImagePath}, models={modelMode}");

using var ocr = new RapidOcr();
using var sessionOptions = RapidOcr.GetDefaultSessionOptions(cli.Threads);

if (cli.HasCustomModels)
{
    foreach (var path in new[] { cli.DetPath, cli.ClsPath, cli.RecPath, cli.KeysPath })
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            Console.Error.WriteLine($"Model file not found: {path}");
            return 2;
        }
    }

    ocr.InitModels(cli.DetPath!, cli.ClsPath!, cli.RecPath!, cli.KeysPath!, sessionOptions);
}
else
{
    // RapidOcrNet 2.0 bundles PP-OCRv5 latin defaults under models/v5/.
    // Use --det/--cls/--rec/--keys for Chinese model testing.
    ocr.InitModels(sessionOptions);
}

var options = RapidOcrOptions.Default with
{
    ReturnWordBox = cli.ReturnWordBox,
    DoAngle = !cli.NoAngle,
};

var sw = Stopwatch.StartNew();
var result = ocr.Detect(cli.ImagePath, options);
sw.Stop();

var lines = result.TextBlocks.Select((block, index) => new LineDto(
    Index: index,
    Text: block.Text,
    AverageScore: block.CharScores is { Length: > 0 } ? block.CharScores.Average() : 0,
    Box: block.BoxPoints.Select(p => new[] { p.X, p.Y }).ToArray()
)).ToArray();

var payload = new OcrDto(
    ModelMode: modelMode,
    ElapsedMs: sw.Elapsed.TotalMilliseconds,
    Text: result.StrRes,
    Lines: lines
);

var jsonOptions = new JsonSerializerOptions { WriteIndented = true };
var json = JsonSerializer.Serialize(payload, jsonOptions);

if (!string.IsNullOrWhiteSpace(cli.JsonOut))
{
    File.WriteAllText(cli.JsonOut, json);
    Console.Error.WriteLine($"Wrote JSON: {cli.JsonOut}");
}
else
{
    Console.WriteLine(json);
}

if (!string.IsNullOrWhiteSpace(cli.DrawOut))
{
    DrawBoxes(cli.ImagePath, cli.DrawOut, result.TextBlocks);
    Console.Error.WriteLine($"Wrote boxed image: {cli.DrawOut}");
}

return 0;

static void DrawBoxes(string imagePath, string outputPath, IEnumerable<TextBlock> blocks)
{
    using var bmp = SKBitmap.Decode(imagePath) ?? throw new InvalidOperationException("Failed to decode image");
    using var canvas = new SKCanvas(bmp);
    using var paint = new SKPaint
    {
        Color = SKColors.Red,
        IsStroke = true,
        StrokeWidth = Math.Max(2, Math.Min(bmp.Width, bmp.Height) / 500f),
        IsAntialias = true,
    };

    foreach (var block in blocks)
    {
        var p = block.BoxPoints.ToArray();
        if (p.Length < 4) continue;
        canvas.DrawLine(p[0], p[1], paint);
        canvas.DrawLine(p[1], p[2], paint);
        canvas.DrawLine(p[2], p[3], paint);
        canvas.DrawLine(p[3], p[0], paint);
    }

    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
    using var fs = File.Create(outputPath);
    bmp.Encode(fs, SKEncodedImageFormat.Png, 100);
}

internal sealed record OcrDto(string ModelMode, double ElapsedMs, string Text, LineDto[] Lines);
internal sealed record LineDto(int Index, string Text, double AverageScore, float[][] Box);

internal sealed class CliOptions
{
    public required string ImagePath { get; init; }
    public string? DetPath { get; init; }
    public string? ClsPath { get; init; }
    public string? RecPath { get; init; }
    public string? KeysPath { get; init; }
    public string? JsonOut { get; init; }
    public string? DrawOut { get; init; }
    public bool ReturnWordBox { get; init; }
    public bool NoAngle { get; init; }
    public int Threads { get; init; }

    public bool HasCustomModels =>
        !string.IsNullOrWhiteSpace(DetPath) ||
        !string.IsNullOrWhiteSpace(ClsPath) ||
        !string.IsNullOrWhiteSpace(RecPath) ||
        !string.IsNullOrWhiteSpace(KeysPath);

    public static CliOptions? Parse(string[] args)
    {
        if (args.Length == 0 || args.Contains("--help") || args.Contains("-h")) return null;

        string? image = null, det = null, cls = null, rec = null, keys = null, json = null, draw = null;
        bool wordBox = false, noAngle = false;
        int threads = 2;

        for (var i = 0; i < args.Length; i++)
        {
            var arg = args[i];
            string Next(string name)
            {
                if (++i >= args.Length) throw new ArgumentException($"Missing value for {name}");
                return args[i];
            }

            switch (arg)
            {
                case "--det": det = Next(arg); break;
                case "--cls": cls = Next(arg); break;
                case "--rec": rec = Next(arg); break;
                case "--keys": keys = Next(arg); break;
                case "--json": json = Next(arg); break;
                case "--draw": draw = Next(arg); break;
                case "--threads": threads = int.TryParse(Next(arg), out var t) ? Math.Max(1, t) : 2; break;
                case "--word-box": wordBox = true; break;
                case "--no-angle": noAngle = true; break;
                default:
                    if (arg.StartsWith("--", StringComparison.Ordinal)) throw new ArgumentException($"Unknown option: {arg}");
                    image ??= arg;
                    break;
            }
        }

        return string.IsNullOrWhiteSpace(image)
            ? null
            : new CliOptions
            {
                ImagePath = image,
                DetPath = det,
                ClsPath = cls,
                RecPath = rec,
                KeysPath = keys,
                JsonOut = json,
                DrawOut = draw,
                ReturnWordBox = wordBox,
                NoAngle = noAngle,
                Threads = threads,
            };
    }

    public static void PrintUsage()
    {
        Console.WriteLine("""
C# RapidOCR PoC

Usage:
  dotnet run -- <image.png> [options]

Default mode uses RapidOcrNet bundled PP-OCRv5 latin models.
For Chinese OCR, download models with scripts/download-chinese-v5.ps1 and pass all model paths.

Options:
  --det <path>       Detection ONNX model path
  --cls <path>       Classification ONNX model path
  --rec <path>       Recognition ONNX model path
  --keys <path>      Recognition dictionary path
  --json <path>      Write JSON output to file instead of stdout
  --draw <path>      Write a PNG copy with red OCR boxes
  --threads <n>      ONNX CPU thread count, default 2
  --word-box         Ask RapidOcrNet for word/character boxes
  --no-angle         Skip angle classifier when text is known upright

Examples:
  dotnet run -- sample.png --draw sample_ocr.png

  dotnet run -- sample.png ^
    --det models/ch-v5/ch_PP-OCRv5_det_mobile.onnx ^
    --cls models/ch-v5/ch_PP-LCNet_x0_25_textline_ori_cls_mobile.onnx ^
    --rec models/ch-v5/ch_PP-OCRv5_rec_mobile.onnx ^
    --keys models/ch-v5/ppocrv5_dict.txt ^
    --json out.json --draw out.png
""");
    }
}
