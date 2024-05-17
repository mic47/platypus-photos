yolo predict -> boxed
yolo classify -> annotations
hugginface text to description -> to text

TODO
* [x] Single image overlay
* [ ] Map overview for gallery
* [ ] Date overview for gallery
* [ ] Separate annotations (expensive from less expensive)? -- point is that  managing location + date + directory is more useful than YOLO
* [ ] Use SQLite (json is not scaling well) -- should do after data format somehow settles
* [ ] More annotations say by time, same dorectory and so on -- i.e. for organization of this shit
* [ ] Ability to recognize moved files -- I probably have some duplicit files -- i.e. if we already had same MD5
* [ ] File management? -- I would like to organize this stuff -- i.e. move same event into some directory
* [ ] More image types -- there are also ORF, png, and so on.
* [ ] ORF -> JPEG mapping -- or maybe I should just delete ORF photos, but would be good to see them first.
* [ ] Soft delete files? I.e. something like move to .deleted directory, or so -- i.e. those that are not selected. Or maybe add some tag that this is not important.

1. Annotate photo "service"
2. Geolocation service
3. Photo DB -> SQLite
4. inotify -> process
5. Track features, version them -> reprocess
6. SQLite -> fuse
