#!/usr/bin/env python
import os, sys, shutil, subprocess, multiprocessing
from pathlib import Path

def run_commands(cwd, args):
	print(subprocess.check_output(args, shell=(os.name == "nt"), text=True, cwd=cwd))


def unzip_url(url, dir, from_name, to_name):
	from io import BytesIO
	from urllib.request import urlopen
	from zipfile import ZipFile
	with urlopen(url) as zipresp:
		with ZipFile(BytesIO(zipresp.read())) as zfile:
			zfile.extractall(str(dir))
			if os.path.exists(dir / to_name):
				os.removedirs(str(dir / to_name))
			os.rename(str(dir / from_name), str(dir / to_name))


def execute(args):
	
	target_file_path = Path(args["target_file_path"])
	library_path = target_file_path.parent
	source_path = args["source_path"]
	library_extension = args["library_extension"]

	platform = args["platform"]
	arch = args["arch"]
	target = args["target"]

	android_ndk_root = args["build_options"]["android_ndk_path"]["value"]

	data_dir = Path(args["gd_settings_dir"])
	bindings_path = data_dir / "godot-cpp"

	bits = "32" if arch in ("32", "x86", "armv7") else "64"

	# Download godot cpp bindings if they are not where they need to be.
	if not bindings_path.exists():
		try:
			unzip_url("https://github.com/godotengine/godot-cpp/archive/master.zip", data_dir, "godot-cpp-master", "godot-cpp")
			unzip_url("https://github.com/godotengine/godot_headers/archive/master.zip", data_dir / "godot-cpp", "godot_headers-master", "godot_headers")
		except:
			e = sys.exc_info()[0]
			raise RuntimeError("%s: Failed to download cpp-bindings!" % e.strerror)

	if platform == "ios" and arch == "arm64v8":
		arch = "arm64"

	# Build godot bindings if there is none.

	static_extension = {
		"windows": "lib",
		"linux": "a",
		"osx": "a",
		"android": "a",
		"ios": "a"
	}

	bindings_file = Path(bindings_path, "bin/libgodot-cpp.%s.%s.%s.%s" % (
		platform,
		target,
		arch,
		static_extension[platform]
	))

	if not bindings_file.exists():
		print("Generating binding library...")
		run_commands(str(bindings_path), [
			"scons",
				"platform=" + platform,
				"bits=" + bits,
				("android_arch=" + arch) if platform == "android" else "",
				("ios_arch=" + arch) if platform == "ios" else "",
				("ANDROID_NDK_ROOT=" + android_ndk_root) if platform == "android" else "",
				"generate_bindings=yes",
				"target=" + target,
				"-j%s" % multiprocessing.cpu_count()
		])

	# Create directory for library files to reside
	try:
		os.makedirs(library_path)
	except: pass

	# Get older dll out of the way.
	lib_name = "%s.%s" % (target_file_path, library_extension)
	try:
		if os.path.exists(lib_name) and platform == "windows" and os.name == "nt":
			# if os.path.exists(lib_name + ".old"):
			# 	os.remove(lib_name + ".old")
			os.replace(lib_name, lib_name + ".old")
	except OSError as e:
		raise OSError("%s: %s" % (e.strerror, lib_name))

	# First we'll copy the SConstruct to the source code.
	shutil.copyfile(
		data_dir / "native_languages/C++/SConstruct",
		library_path / "../SConstruct"
	)

	# Build source code
	print("Building source")
	run_commands(str(library_path / ".."), [
		"scons",
			"platform=" + platform,
			"bits=" + bits,
			"target=" + target,
			("android_arch=" + arch) if platform == "android" else "",
			("ios_arch=" + arch) if platform == "ios" else "",
			("ANDROID_NDK_ROOT=" + android_ndk_root) if platform == "android" else "",
			"cpp_bindings_path=" + ("%s/" % bindings_path),
			"source_path=" + str(source_path),
			"target_path=" + str(library_path) + "/",
			"target_name=" + str(target_file_path.name),
			"-j%s" % multiprocessing.cpu_count()
	])

	# Remove SConstruct once we're done.
	os.remove(library_path / "../SConstruct")
