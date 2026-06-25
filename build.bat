@echo off
chcp 65001 >nul
echo ====================================
echo   SnapOCR 打包脚本
echo ====================================
echo.

echo [1/3] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo 清理完成
echo.

echo [2/3] 开始打包 (这可能需要几分钟)...
pyinstaller SnapOCR.spec
if errorlevel 1 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)
echo 打包完成
echo.

echo [3/3] 生成便携模式标记文件...
echo. > dist\SnapOCR\portable.flag
echo 便携模式已启用
echo.

echo ====================================
echo   打包成功！
echo ====================================
echo.
echo 可执行文件位置: dist\SnapOCR\SnapOCR.exe
echo.
echo 整个 dist\SnapOCR\ 文件夹即为完整程序，可以直接复制分发。
echo 已自动启用便携模式，所有数据保存在 data\ 子目录。
echo.
pause
