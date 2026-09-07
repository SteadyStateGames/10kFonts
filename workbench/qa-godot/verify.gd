extends SceneTree
func _initialize():
    var args = OS.get_cmdline_user_args()
    var catalog_path = args[0]
    var folder = catalog_path.get_base_dir()
    var rows = JSON.parse_string(FileAccess.get_file_as_string(catalog_path))
    var tested = 0
    var core_count = 0
    for row in rows:
        var font = FontFile.new()
        var error = font.load_dynamic_font(folder.path_join(row.ttf))
        if error != OK:
            push_error("Load failure: " + row.id)
            quit(1)
            return
        for code in row.codepoint_list:
            if not font.has_char(int(code)):
                push_error("Missing glyph: " + row.id + " / " + str(code))
                quit(1)
                return
        var text = "An army awaits at dawn. 0123456789"
        if row.collection_tier == "Core":
            core_count += 1
            text += " Café, Straße, piñata."
        for size in [16,24,48]:
            var measured = font.get_string_size(text,HORIZONTAL_ALIGNMENT_LEFT,-1,size)
            if measured.x <= 0 or measured.y <= 0:
                push_error("Shaping failure: " + row.id)
                quit(1)
                return
        tested += 1
        if tested % 500 == 0:
            print(str(tested) + " fonts loaded and shaped in Godot")
    var result = {"godot_version":Engine.get_version_info().string,"ttfs_loaded":tested,"core_fonts":core_count,"every_catalog_codepoint_found":true,"text_sizes":[16,24,48],"scope":"Headless FontFile loading and string shaping; not in-game visual or screenshot validation."}
    var output = FileAccess.open(folder.path_join("godot-validation.json"),FileAccess.WRITE)
    output.store_string(JSON.stringify(result,"\t"))
    output.close()
    print(JSON.stringify(result))
    quit()

