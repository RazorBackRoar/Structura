STRUCTURA UI README
===================

Purpose
-------
Structura is a single-window folder analyzer with a macOS-inspired desktop feel.

Primary workflow:
1. Choose or drop one root folder.
2. Let Structura scan the folder tree.
3. Browse folders in the left sidebar.
4. Review subtree-aware metrics, extension distribution, and extension counts on the right.
5. Optionally sort top-level image and video files in the active root folder.

This is not a media browser, editor, or file manager clone.
It is an analyzer-first utility with a secondary root-level media sorting action.


Product Truths
--------------
- One active root folder at a time
- Recursive analysis across all file types
- Left sidebar is the primary folder navigator
- Right pane is the primary analysis surface
- Sorting remains root-only, top-level-only, and media-only
- Hidden files can be included or excluded
- The UI should feel native, calm, readable, and practical


Core UI Structure
-----------------
Top chrome:
- App title: Structura
- Selected root folder path
- Choose Folder button
- Hidden: On / Off toggle

Main body:
- Left sidebar: recursive folder structure tree
- Right pane:
  - selected subtree heading and path
  - metric tiles for total files, total size, and total folders
  - extension filter
  - file-type distribution chart
  - top file extensions bar list
  - extension breakdown table
  - secondary sort panel

Empty state:
- Compact drop/select prompt inside the right pane

Scanning state:
- Compact progress state in the same right-pane area


Interaction Rules
-----------------
- Selecting a folder or file in the tree updates the right-side analysis
- Choosing a new root folder replaces the current workspace
- Dropping multiple folders should resolve to one active root folder
- Sorting never follows the subtree selection; it always targets the active root folder


Sort Rules
----------
- Sort by extension
- Only top-level image and video files are eligible
- Subfolders are untouched
- Non-media files are ignored
- Scope modes:
  - Both
  - Images
  - Videos


Visual Direction
----------------
- Native macOS utility, not a web dashboard clone
- Bright surfaces, soft borders, restrained blue accents
- Strong hierarchy, generous whitespace, quiet typography
- No gimmicky chrome, no futuristic effects, no analytics clutter

Result card detail examples:
- "Creates folders: MOV, MP4, JPG, PNG, HEIC"
- "12 other files ignored"
- "3 subfolders left alone"
- "hidden files on"
- "hidden files off"

Sort dialog:
- "Sort "<folder name>""
- "Top-level image and video files will be moved into folders named after their extension. Subfolders and non-media files stay where they are."
- Cancel
- Sort


What The UI Should Feel Like
----------------------------
The UI should feel:
- simple
- obvious
- readable
- fast
- calm
- utilitarian

It should NOT feel like:
- a dashboard
- a media manager
- a file explorer clone
- a heavy analytics app
- a fancy chrome or futuristic interface

The user should understand the app in 3 seconds:
"Drop folder. Review extension counts. Click Sort."


What To Preserve In Any Redesign
--------------------------------
These are the essential product truths:
- The app is a folder sorting tool.
- The main action is dropping a folder.
- The second action is clicking Sort.
- Sorting is by extension.
- Only top-level image/video files are moved.
- Non-media files stay put.
- Subfolders stay put.
- Hidden files can be included or excluded.
- The UI should make extension folders obvious.


What To Remove Or Avoid
-----------------------
Avoid these in future UI directions:
- charts
- analytics-style widgets
- redundant metrics
- split-pane file browser layouts
- decorative cards everywhere
- extra sections that repeat the same information
- overly technical copy
- visual noise

The UI should not make the user hunt for the Sort action.


Ideal Simplified UI
-------------------
Best-case layout:

1. Top bar
   - App name
   - Open Folder
   - Hidden toggle

2. Main drop area
   - Large drop target
   - One sentence explanation

3. Scan result block
   - Folder name
   - Short explanation:
     "This folder has 61 sortable files in 2 extensions."
   - Simple list or table:
     MOV - 52
     MP4 - 9
   - Small note:
     "Other files ignored. Subfolders untouched."
   - Primary button:
     Sort

4. Optional confirmation dialog
   - Keep it short
   - Confirm the folders that will be created


Stitch Brief
------------
Use this if you want to recreate the app UI in Stitch:

"Design a very simple desktop utility interface for an app called Structura.
Its only job is to help users sort top-level image and video files inside a folder by file extension.

Primary workflow:
1. User drops a folder into the app.
2. App scans the folder.
3. App shows which sortable extensions exist at the top level, for example MOV, MP4, JPG, JPEG, PNG, HEIC.
4. User clicks a primary Sort button.
5. The app creates subfolders named after those extensions and moves matching top-level files into them.

Do not design this like a dashboard.
Do not use charts.
Do not use complex sidebars or file browser panes.
Do not make it look futuristic or over-styled.

The interface should be minimal, readable, obvious, and calm.
It should feel like a focused utility.

Include:
- a top bar with app name, Open Folder button, and Hidden Files toggle
- a large drag-and-drop area
- a simple result panel
- a plain list of extension counts
- one strong Sort button
- a short note explaining that only top-level image/video files are moved and subfolders are untouched

Use short labels and plain language.
Optimize for clarity over decoration."


Technical Notes
---------------
Main source files:
- src/main.py
- Structura.py

Important current logic:
- Recursive scan exists for folder analysis.
- Sort action only moves top-level sortable files.
- Extension folders are uppercase versions of extensions.


If You Want Future Improvements
-------------------------------
Good next improvements:
- sort immediately without confirmation dialog
- show a preview line like:
  "Will create: MOV, MP4, JPG"
- add a "Sorted successfully" success message
- let users choose whether to sort images only, videos only, or both
- let users preview ignored files

Bad future improvements:
- thumbnails
- charts
- complex navigation
- too many panels
- extra metadata views
