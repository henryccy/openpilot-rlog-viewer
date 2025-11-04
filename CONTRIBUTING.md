# Contributing to openpilot Windows Log Viewer

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

### Prerequisites
- Python 3.10 or higher
- Git
- Windows 10/11 (for testing)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/openpilot-log-viewer.git
   cd openpilot-log-viewer
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run from Source**
   ```bash
   python main.py
   ```

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Screenshots (if applicable)
- Log file contents (`oplog_viewer.log`)
- System information (Windows version, Python version)

### Suggesting Features

Feature requests are welcome! Please:
- Check existing issues first to avoid duplicates
- Clearly describe the feature and its use case
- Explain why this feature would be useful to other users

### Code Contributions

#### Pull Request Process

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write clean, readable code
   - Follow existing code style
   - Add comments for complex logic
   - Update documentation if needed

3. **Test Your Changes**
   - Test with real openpilot logs
   - Verify no regressions in existing features
   - Test on Windows 10 and 11 if possible

4. **Commit**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then open a Pull Request on GitHub.

#### Code Style

- **Python**: Follow PEP 8 guidelines
- **Line Length**: Maximum 120 characters
- **Docstrings**: Use for all public functions and classes
- **Type Hints**: Encouraged but not required
- **Comments**: Write clear comments for complex logic

#### Example

```python
def parse_signal_data(signal_name: str, data: bytes) -> dict:
    """
    Parse signal data from raw bytes.

    Args:
        signal_name: Name of the signal to parse
        data: Raw byte data

    Returns:
        Dictionary containing parsed signal values
    """
    # Implementation here
    pass
```

### Areas for Contribution

We especially welcome contributions in these areas:

#### High Priority
- **Performance Improvements**: Optimize data loading and plotting
- **Bug Fixes**: Fix any issues you encounter
- **Documentation**: Improve user guides and code comments
- **Testing**: Add unit tests and integration tests

#### Medium Priority
- **New Features**: Video export, advanced filtering, etc.
- **UI Improvements**: Better layouts, themes, icons
- **Internationalization**: Add more language translations
- **DBC Management**: Better DBC file handling

#### Low Priority
- **Code Refactoring**: Improve code structure
- **Build System**: Improve compilation process
- **CI/CD**: Add automated testing

## Translation Contributions

### Adding UI Translations

1. **Edit Translation File**
   - For Chinese: `i18n/zh_TW.json`
   - For new language: Create `i18n/<language_code>.json`

2. **Format**
   ```json
   {
     "English String": "翻譯後的字串",
     "Another String": "另一個翻譯"
   }
   ```

3. **Test**
   - Restart application
   - Switch language in `View → Language`
   - Verify all strings are translated

### Adding Signal Translations

1. **Edit Signal Translation File**
   - For Chinese: `data/translations/signals_zh_TW.json`

2. **Format**
   ```json
   {
     "carState.vEgo": "車速",
     "carState.aEgo": "加速度"
   }
   ```

## DBC Contributions

If you have DBC files for additional car models:

1. Place DBC file in `data/dbc/`
2. Test importing with `Tools → Import Signal Definitions`
3. Submit PR with the DBC file and a description of the vehicle

## Documentation Contributions

Documentation improvements are always welcome:

- **README**: Improve installation instructions, add examples
- **User Guide**: Add tips, clarify steps, add screenshots
- **Build Guide**: Improve compilation instructions
- **Code Comments**: Add or improve inline documentation

## Questions?

- Open an issue with the `question` label
- Check existing issues and discussions
- Be respectful and patient

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what is best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment, discriminatory language, or personal attacks
- Trolling or insulting comments
- Publishing others' private information
- Any conduct inappropriate in a professional setting

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

---

**Thank you for contributing to openpilot Windows Log Viewer!** 🎉
