# Chapters

Drop a chapter here as a UTF-8 `.txt` file and push. The **Webtoon** GitHub Action
turns every new or changed chapter into a webtoon and attaches it to the run as a
downloadable artifact (`webtoons-<run number>`, one folder per chapter).

Options can go in the first line of the file, starting with `#webtoon:`:

```
#webtoon: --lang ja --max-panels 40
第一章 ...
```

Allowed options: `--lang en|zh|ja`, `--max-panels N`, `--no-letter`.
The line is removed before the chapter is sent to Claude.
