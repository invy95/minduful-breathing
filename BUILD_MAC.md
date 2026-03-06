# 呼吸泡泡 Mac 版 — 打包操作说明

请在 **Mac 电脑**上按以下步骤操作，完成后会生成可直接运行的 Mac 版呼吸泡泡。

---

## 第一步：安装 Python（如已安装可跳过）

打开「终端」（Terminal），输入以下命令检查是否已安装 Python 3：

```bash
python3 --version
```

如果显示 `Python 3.x.x` 则已安装，跳到第二步。

如果未安装，请先安装 Homebrew，再安装 Python：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
```

---

## 第二步：解压并进入项目目录

将收到的 zip 文件解压，然后在终端中进入解压后的文件夹：

```bash
cd ~/Downloads/mindful-breathing-mac-source
```

（路径根据你实际解压位置调整）

---

## 第三步：安装依赖

```bash
pip3 install pyinstaller pillow pystray python-dotenv supabase httpx psutil
```

如果提示权限不足，在前面加 `sudo`：

```bash
sudo pip3 install pyinstaller pillow pystray python-dotenv supabase httpx psutil
```

---

## 第四步：一键打包

```bash
python3 build_release_mac.py
```

等待打包完成，大约需要 1-3 分钟。看到 `Mac 版打包完成` 即表示成功。

---

## 第五步：获取打包结果

打包完成后，结果在 `dist` 文件夹中：

- **`dist/呼吸泡泡-mac.zip`** — 可直接发回给我的最终 zip 文件
- **`dist/呼吸泡泡/`** — 解压后的应用目录（可先测试一下能不能正常运行）

### 测试运行

```bash
cd dist/呼吸泡泡
./呼吸泡泡
```

如果 macOS 提示"无法验证开发者"，请右键点击「呼吸泡泡」→ 选择「打开」。

---

## 第六步：发回结果

请将 **`dist/呼吸泡泡-mac.zip`** 文件发回给我即可！

---

## 常见问题

**Q: 提示 `command not found: pip3`？**
A: 试试 `python3 -m pip install ...` 代替 `pip3 install ...`

**Q: 打包报错 `ModuleNotFoundError`？**
A: 确保第三步的依赖全部安装成功，可以再运行一次安装命令。

**Q: 运行时提示"文件已损坏"？**
A: 在终端执行：`xattr -cr dist/呼吸泡泡/呼吸泡泡`，然后重新运行。
