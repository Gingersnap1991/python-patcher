import shutil
import sys, os, platform, subprocess, json
import threading
import time
from gameScanner import ModFile

try:
	"".decode("utf-8")
	def decodeStr(string):
		return string.decode("utf-8")
except AttributeError:
	def decodeStr(string):
		return string

try:
	from urllib.request import urlopen, Request
	from urllib.error import HTTPError
except ImportError:
	from urllib2 import urlopen, Request, HTTPError

# Python 2 Compatibility
try: input = raw_input
except NameError: pass

COMMON_DEBUG_MODE = False

def printErrorMessage(text):
	"""
	Prints message in red if stdout is a tty
	"""
	if sys.stdout.isatty:
		print("\x1b[1m\x1b[31m" + text + "\x1b[0m")
	else:
		print(text)

def exitWithError():
	""" On Windows, prevent window closing immediately when exiting with error. Other plaforms just exit. """
	print("ERROR: The installer cannot continue. Press any key to exit...")
	if IS_WINDOWS:
		input()
	sys.exit(1)

# You can use the 'exist_ok' of python3 to do this already, but not in python 2
def makeDirsExistOK(directoryToMake):
	try:
		os.makedirs(directoryToMake)
	except OSError:
		pass

def tryShowFolder(path):
	"""
	Tries to show a given path in the system file browser
	NOTE: this function call does not block! (uses subprocess.Popen)
	:param path: the path to show
	:return: true if successful, false otherwise
	"""
	try:
		if IS_WINDOWS:
			return subprocess.Popen(["explorer", path]) == 0
		elif IS_MAC:
			return subprocess.Popen(["open", path]) == 0
		else:
			return subprocess.Popen(["xdg-open", path]) == 0
	except:
		return False

def findWorkingExecutablePath(executable_paths, flags):
	"""
	Try to execute each path in executable_paths to see which one can be called and returns exit code 0
	The 'flags' argument is any extra flags required to make the executable return 0 exit code
	:param executable_paths: a list [] of possible executable paths (eg. "./7za", "7z")
	:param flags: any extra flags like "-h" required to make the executable have a 0 exit code
	:return: the path of the valid executable, or None if no valid executables found
	"""
	with open(os.devnull, 'w') as os_devnull:
		for path in executable_paths:
			try:
				if subprocess.call([path, flags], stdout=os_devnull) == 0:
					print("Found valid executable:", path)
					return path
			except:
				pass

	return None
################################################## Global Variables#####################################################

# The installer info version this installer is compatibile with
# Increment it when you make breaking changes to the json files
JSON_VERSION = 1

###################################### Executable detection and Installation ###########################################

# If you double-click on the file in Finder on macOS, it will not open with a path that is near the .py file
# Since we want to properly find things like `./aria2c`, we should move to that path first.
dirname = os.path.dirname(sys.argv[0])
if dirname.strip():
	os.chdir(dirname)

# Define constants used throughout the script. Use function calls to enforce variables as const
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

# Set os string matching string used in the JSON file, for convenience
OS_STRING = "win"
if IS_LINUX:
	OS_STRING = "linux"
elif IS_MAC:
	OS_STRING = "mac"

#query available executables. If any installation of executables is done in the python script, it must be done
#before this executes
ARIA_EXECUTABLE = findWorkingExecutablePath(["./aria2c", "./.aria2c", "aria2c"], '-h')
if ARIA_EXECUTABLE is None:
	# TODO: automatically download and install dependencies
	print("ERROR: aria2c executable not found (aria2c). Please install the dependencies for your platform.")
	exitWithError()

SEVEN_ZIP_EXECUTABLE = findWorkingExecutablePath(["./7za", "./.7za", "7za", "./7z", "7z"], '-h')
if SEVEN_ZIP_EXECUTABLE is None:
	# TODO: automatically download and install dependencies
	print("ERROR: 7-zip executable not found (7za or 7z). Please install the dependencies for your platform.")
	exitWithError()

#TODO: capture both stdout and stderr
def runProcessOutputToTempFile(arguments):
	print("----- BEGIN EXECUTING COMMAND: [{}] -----".format(" ".join(arguments)))

	# need universal_newlines=True so stdout is opened in normal. However, this might result in garbled japanese(unicode) characters!
	# to fix this properly, you would need to make a custom class which takes in raw bytes using stdout.read(10)
	# and then periodically convert newline delimited sections of the text to utf-8 (or whatever encoding), and catch bad encoding errors
	# See comments on https://stackoverflow.com/a/15374326/848627 and answer https://stackoverflow.com/a/48880977/848627
	proc = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

	def readUntilEOF(proc, fileLikeObject):
		while proc.poll() is None:
			try:
				fileLikeObject.flush()
				while True:
					line = fileLikeObject.readline()

					if line:
						print(line)
					else:
						break
			except:
				#reduce cpu usage if some exception is continously thrown
				time.sleep(.1)

	# Monitor stderr on one thread, and monitor stdout on main thread
	t = threading.Thread(target=readUntilEOF, args=(proc, proc.stderr))
	t.start()

	readUntilEOF(proc, proc.stdout)

	print("--------------- EXECUTION FINISHED ---------------\n")
	return proc.returncode

#when calling this function, use named arguments to avoid confusion!
def aria(downloadDir=None, inputFile=None, url=None, followMetaLink=False, useIPV6=False):
	"""
	Calls aria2c with some default arguments:
	TODO: list what each default argument does as comments next to arguments array?

	:param downloadDir: The directory to store the downloaded file(s)
	:param inputFile: The path to a file containing multiple URLS to download (see aria2c documentation)
	:return Returns the exit code of the aria2c call
	"""
	arguments = [
		ARIA_EXECUTABLE,
		"--file-allocation=none",
		'--continue=true',
		'--retry-wait=5',
		'-m 0', # max number of retries (0=unlimited). In some cases, like server rejects download, aria2c won't retry.
		'-x 8', # max connections to the same server
		'-s 8', # Split - Try to use N connections per each download item
		'-j 1', # max concurrent download items (eg number of separate urls which can be downloaded in parallel)
	]

	if followMetaLink:
		arguments.append('--follow-metalink=mem')
		arguments.append('--check-integrity=true')  # check integrity when using metalink
	else:
		arguments.append('--follow-metalink=false')

	if not useIPV6:
		arguments.append('--disable-ipv6=true')

	#Add an extra command line argument if the function argument has been provided
	if downloadDir:
		arguments.append('-d ' + downloadDir)

	if inputFile:
		arguments.append('--input-file=' + inputFile)

	if url:
		arguments.append(url)

	# with open('seven_zip_stdout.txt', "w", buffering=100) as outfile:
	# 	return subprocess.call(arguments, stdout=outfile)
	return runProcessOutputToTempFile(arguments)

def sevenZipExtract(archive_path, outputDir=None):
	arguments = [SEVEN_ZIP_EXECUTABLE,
				 "x",
				 archive_path,
				 "-aoa",  # overwrite All existing files without prompt (-ao means 'overwrite mode', a means 'All')
				 "-bso1", # redirect standard Output messages to stdout
				 "-bsp1", # redirect Progress update messages to stdout
				 "-bse2", # redirect Error messages to stderr
				 ]

	if outputDir:
		arguments.append('-o' + outputDir)
	return runProcessOutputToTempFile(arguments)

def getModList(jsonURL):
	"""
	Gets the list of available mods from the 07th Mod server

	:return: A list of mod info objects
	:rtype: list[dict]
	"""
	try:
		file = urlopen(Request(jsonURL, headers={"User-Agent": ""}))
	except HTTPError as error:
		print(error)
		print("Couldn't reach 07th Mod Server to download patch info")
		print("Note that we have blocked Japan from downloading (VPNs are compatible with this installer, however)")
		exitWithError()

	info = json.load(file)
	file.close()
	try:
		version = info["version"]
		if version > JSON_VERSION:
			printErrorMessage("Your installer is out of date.")
			printErrorMessage("Please download the latest version of the installer and try again.")
			print("\nYour installer is compatible with mod listings up to version " + str(JSON_VERSION) + " but the latest listing is version " + str(version))
			exitWithError()
	except KeyError:
		print("Warning: The mod info listing is missing a version number.  Things might not work.")
		return info
	return info["mods"]

def printSupportedGames(modList):
	"""
	Prints a list of games that have mods available for them
	:param list[dict] modList: The list of available mods
	"""
	print("Supported games:")
	for game in set(x["target"] for x in modList):
		print("  " + game)

def makeExecutable(executablePath):
	current = os.stat(executablePath)
	os.chmod(executablePath, current.st_mode | 0o111)

def getMetalinkFilenames(url, downloadDir):
	import xml.etree.ElementTree as ET

	metalinkFileName = os.path.basename(url)
	metalinkFileFullPath = os.path.join(downloadDir, metalinkFileName)

	aria(downloadDir, url=url)

	tree = ET.parse(metalinkFileFullPath)
	root = tree.getroot()

	# return the 'name' attribute of each 'file' node.
	# ignore namespaces by removing the {stuff} part of the tag
	filenames = []
	for fileNode in root.iter():
		tagNoNamespace = fileNode.tag.split('}')[-1]
		if tagNoNamespace == 'file':
			filenames.append(fileNode.attrib['name'])

	return filenames

def extractOrCopyFile(filename, sourceFolder, destinationFolder, copiedOutputFileName=None):
	makeDirsExistOK(destinationFolder)
	sourcePath = os.path.join(sourceFolder, filename)
	if COMMON_DEBUG_MODE:
		print("Copying or Extracting [{}] into [{}]".format(sourcePath, destinationFolder))
		return

	if '.7z' in filename.lower() or '.zip' in filename.lower():
		if sevenZipExtract(sourcePath, outputDir=destinationFolder) != 0:
			print("ERROR - could not extract [{}]. Installation Stopped".format(sourcePath))
			exitWithError()
	else:
		try:
			shutil.copy(sourcePath, os.path.join(destinationFolder, copiedOutputFileName if copiedOutputFileName else filename))
		except shutil.SameFileError:
			print("Source and Destination are the same [{}]. No action taken.".format(sourcePath))



class DownloaderAndExtractor:
	"""
	####################################################################################################################
	#
	# Downloads and/or Extracts a list of ModFile objects
	#
	# Usage: Call 'download' then 'extract'.
	# If you have metalinks in your path, callin only 'extract' may require fetching the metafiles to determine what
	# to extract
	#
	# a ModFile is an object which contains a url and a priority (int). The priority extraction order.
	# See the modfile class for more information
	# You can use the FullInstallConfig.buildFileListSorted() to generate the modFileList, which handles
	# ordering the ModFiles and using different modfiles on different operating systems/steam/mg installs
	#
	# Metafile Handling:
	# - For metafiles, we need to look for filenames within each metafile to know what to extract
	# - The order of the download and extraction is maintained through the list ordering.
	#
	# Archive Handling:
	# - Archives will be extracted in to the downloadTempDir folder
	#
	# Other file handling:
	# - Any other types of files will be copied (overwritten) from the downloadTempDir to the extractionDir
	# - If the path of the file is the same as the destination (a no op), the file won't be copied (it will do nothing)
	#
	# Folder Creation:
	# - All folders will be created if they don't already exist
	#
	# Failure Modes:
	# - if any downloads or extractions fail, the script will terminate
	# - TODO: could improve success rate by retrying aria downloads multiple times
	#
	####################################################################################################################

	:param modFileList:		The a list of ModFile objects which will be downloaded and/or extracted
	:param downloadTempDir: The folder where downloads will be saved
	:param extractionDir:	The folder where archives will be extracted to, and where any files will be copied to
	:return:
	"""

	def __init__(self, modFileList, downloadTempDir, extractionDir):
		# type: ([ModFile], str, str) -> None
		self.modFileList = modFileList
		self.downloadTempDir = downloadTempDir
		self.extractionDir = extractionDir
		self.downloadAndExtractionListsBuilt = False

	def buildDownloadAndExtractionList(self):
		# build file list
		self.downloadList = []
		self.extractList = []

		print("\n Building Download and Extraction list:")
		for i, file in enumerate(self.modFileList):
			name, ext = os.path.splitext(file.url)

			if ext == '.meta4' or ext == '.metalink':
				metalinkFilenames = getMetalinkFilenames(file.url, self.downloadTempDir)
				print("Metalink contains: ", metalinkFilenames)
				self.downloadList.append(file.url)
				self.extractList.extend(metalinkFilenames)
			else:
				self.downloadList.append(file.url)
				self.extractList.append(os.path.basename(file.url))

		print("\nFirst these files will be downloaded:")
		print('\n - '.join([''] + self.downloadList))
		print("\nThen these files will be extracted or copied:")
		print('\n - '.join([''] + self.extractList))
		print()

		self.downloadAndExtractionListsBuilt = True

	def download(self):
		if not self.downloadAndExtractionListsBuilt:
			self.buildDownloadAndExtractionList()

		# download all urls to the download temp folder
		makeDirsExistOK(self.downloadTempDir)
		makeDirsExistOK(self.extractionDir)

		for url in self.downloadList:
			print("Downloading [{}] -> [{}]".format(url, self.downloadTempDir))
			if not COMMON_DEBUG_MODE and aria(self.downloadTempDir, url=url, followMetaLink=True) != 0:
				print("ERROR - could not download [{}]. Installation Stopped".format(url))
				exitWithError()

	def extract(self):
		if not self.downloadAndExtractionListsBuilt:
			self.buildDownloadAndExtractionList()

		# extract or copy all files from the download folder to the game directory
		for filename in self.extractList:
			fileNameNoExt, extension = os.path.splitext(filename)

			extractOrCopyFile(filename,
							  self.downloadTempDir,
							  self.extractionDir,
							  copiedOutputFileName=(fileNameNoExt + '.u') if '.utf' in extension else filename)