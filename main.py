import sys, sqlite3, time, datetime, os, hashlib
from PySide import QtCore, QtGui

import mbdbdecoding, plistutils, magic

from main_window import Ui_MainWindow
from sqlite_widget import Ui_SqliteWidget
from image_widget import Ui_ImageWidget
from hex_widget import Ui_HexWidget


class HexWidget(QtGui.QWidget):

	page = 0
	pageSize = 1024
	
	FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
	def hex2string(self, src, length=8):
		N=0; result=''
		while src:
			s,src = src[:length],src[length:]
			hexa = ' '.join(["%02X"%ord(x) for x in s])
			s = s.translate(self.FILTER)
			N+=length
			result += s
		return result

	def hex2numsArray(self, src, length=1):
		N=0; result=[]
		while src:
		   s,src = src[:length],src[length:]
		   hexa = ' '.join(["%02X"%ord(x) for x in s])
		   s = s.translate(self.FILTER)
		   N+=length
		   result.append(hexa)
		return result

	def setTitle(self, title):
		self.setWindowTitle(title)

	def __init__(self, fileName = None):
		QtGui.QWidget.__init__(self)
		
		self.ui = Ui_HexWidget()
		self.ui.setupUi(self)
		
		self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
		
		self.fileName = fileName

		QtCore.QObject.connect(self.ui.buttonLeft, QtCore.SIGNAL("clicked()"), self.leftButtonClicked)
		QtCore.QObject.connect(self.ui.buttonRight, QtCore.SIGNAL("clicked()"), self.rightButtonClicked)
		
		self.updateTable()
		
	
	def updateTable(self):	
	
		try:
			fh = open(self.fileName, 'rb')
			fh.seek(self.pageSize*self.page)
			text = fh.read(self.pageSize)
			
			self.ui.hexTable.setRowCount(int(self.pageSize / 16))
			
			print len(text)
		
			row = 0
			while text:
				s, text = text[:16],text[16:]
				
				col = 0
				for element in self.hex2numsArray(s):
					
					newItem = QtGui.QTableWidgetItem(str(element))
					self.ui.hexTable.setItem(row, col, newItem)				
					col = col + 1
				
				newItem = QtGui.QTableWidgetItem(str(self.hex2string(s)))
				self.ui.hexTable.setItem(row, col, newItem)
				
				row = row + 1
			
			fh.close()
		
		except:
			print "Unexpected error:", sys.exc_info()

		self.ui.hexTable.resizeColumnsToContents()		
		
	def leftButtonClicked(self):
		if (self.page > 0):
			self.page = self.page - 1
			self.updateTable()

	def rightButtonClicked(self):
		self.page = self.page + 1
		self.updateTable()	
	

class ImageWidget(QtGui.QWidget):

	def __init__(self, fileName = None):
		QtGui.QWidget.__init__(self)
		
		self.ui = Ui_ImageWidget()
		self.ui.setupUi(self)
		
		self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
		
		self.fileName = fileName
		
		pic = QtGui.QPixmap(fileName).scaled(300, 300, QtCore.Qt.KeepAspectRatio)
			
		view = self.ui.imageLabel
		view.setPixmap(pic) 
		view.show() 
		
		#retrieve EXIF data

		from PIL import Image
		from PIL.ExifTags import TAGS

		self.ui.exifTable.clear()
		
		self.ui.exifTable.setHorizontalHeaderItem(0, QtGui.QTableWidgetItem("Tag"))
		self.ui.exifTable.setHorizontalHeaderItem(1, QtGui.QTableWidgetItem("Descr"))
		self.ui.exifTable.setHorizontalHeaderItem(2, QtGui.QTableWidgetItem("Value"))

		try:
			i = Image.open(self.fileName)
			info = i._getexif()
			
			self.ui.exifTable.setRowCount(len(info))
			
			row = 0
			for tag, value in info.items():
				decoded = TAGS.get(tag, tag)

				newItem = QtGui.QTableWidgetItem(str(tag))
				self.ui.exifTable.setItem(row, 0, newItem)
				
				newItem = QtGui.QTableWidgetItem(decoded)
				self.ui.exifTable.setItem(row, 1, newItem)

				if (type(value) == type((1,2))):
					value = "%.3f (%i / %i)"%(float(value[0]) / float(value[1]), value[0], value[1])
				
				newItem = QtGui.QTableWidgetItem(str(value))
				self.ui.exifTable.setItem(row, 2, newItem)
				
				row = row + 1
		
			self.ui.exifTable.resizeColumnsToContents()	
				
		except:
			pass
		
	def setTitle(self, title):
		self.setWindowTitle(title)


class SqliteWidget(QtGui.QWidget):

	itemsPerScreen = 100
	pageNumber = 0
	currentTableOnDisplay = None

	FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
	def dump(self, src, length=8, limit=10000):
		N=0; result=''
		while src:
			s,src = src[:length],src[length:]
			hexa = ' '.join(["%02X"%ord(x) for x in s])
			s = s.translate(self.FILTER)
			result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
			N+=length
			if (len(result) > limit):
				src = "";
				result += "(analysis limit reached after %i bytes)"%limit
		return result


	def __init__(self, fileName = None):
		QtGui.QWidget.__init__(self)
		
		self.ui = Ui_SqliteWidget()
		self.ui.setupUi(self)
		
		self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
		
		QtCore.QObject.connect(self.ui.tablesList, QtCore.SIGNAL("itemSelectionChanged()"), self.tableClicked)
		QtCore.QObject.connect(self.ui.buttonLeft, QtCore.SIGNAL("clicked()"), self.leftButtonClicked)
		QtCore.QObject.connect(self.ui.buttonRight, QtCore.SIGNAL("clicked()"), self.rightButtonClicked)
		
		self.ui.tablesList.setColumnWidth(0,150)
		self.ui.tablesList.setColumnWidth(1,30)
		
		self.fileName = fileName
		
		tempdb = sqlite3.connect(self.fileName)
		
		try:
			tempcur = tempdb.cursor() 
			tempcur.execute("SELECT name FROM sqlite_master WHERE type=\"table\"")
			tables_list = tempcur.fetchall();
			
			for i in tables_list:
				table_name = str(i[0])
				
				recordCount = 0
				try:
					tempcur.execute("SELECT count(*) FROM %s" % table_name);
					elem_count = tempcur.fetchone()
					recordCount = int(elem_count[0])
	
				except:
					#probably a virtual table?
					pass
					
				newElement = QtGui.QTreeWidgetItem(None)
				newElement.setText(0, table_name)
				newElement.setText(1, str(recordCount))
				
				self.ui.tablesList.addTopLevelItem(newElement)
	
			tempdb.close()		
			
		except:
			print("\nUnexpected error: %s"%sys.exc_info()[1])
			self.close()
		
	
	def setTitle(self, title):
		self.setWindowTitle(title)
	
	def leftButtonClicked(self):
		if (self.pageNumber > 0):
			self.pageNumber = self.pageNumber - 1
			self.updateTableDisplay()

	def rightButtonClicked(self):
		self.pageNumber = self.pageNumber + 1
		self.updateTableDisplay()	
	
	def tableClicked(self):
		currentSelectedElement = self.ui.tablesList.currentItem()
		if (currentSelectedElement): pass
		else: return
		
		tableName = currentSelectedElement.text(0)
		self.currentTableOnDisplay = tableName
		self.pageNumber = 0
		
		self.updateTableDisplay()
		
		
	def updateTableDisplay(self):

		tableName = self.currentTableOnDisplay
		if (tableName == None): return

		if (os.path.exists(self.fileName)):
			seltabledb = sqlite3.connect(self.fileName)
			
			try:
				seltablecur = seltabledb.cursor() 
			
				# read selected table indexes
				seltablecur.execute("PRAGMA table_info(%s)" % tableName)
				seltable_fields = seltablecur.fetchall();
				
				self.ui.tableContent.clear()
				
				self.ui.tableContent.setColumnCount(len(seltable_fields))
				
				# header (fields names)
				fieldsNames = []
				index = 0
				for record in seltable_fields:
				
					#import unicodedata
					try:
						value = str(record[1]) + "\n" + str(record[2])
					except:
						value = record[1].encode("utf8", "replace") + " (decoded unicode)"
				
					newItem = QtGui.QTableWidgetItem(value)
					self.ui.tableContent.setHorizontalHeaderItem(index, newItem)
					index = index + 1
					fieldsNames.append(str(record[1]))
				
				seltablecur.execute("SELECT * FROM %s LIMIT %i OFFSET %i" % (tableName, self.itemsPerScreen, self.pageNumber * self.itemsPerScreen))
				records = seltablecur.fetchall();
				
				self.ui.tableContent.setRowCount(len(records))
				
				self.ui.recordLabel.setText("Records %i-%i"%(self.pageNumber*self.itemsPerScreen+1, (self.pageNumber+1)*self.itemsPerScreen))
				
				rowIndex = 0
				for record in records:
				
					columnIndex = 0
					for field in record:
					
						#import unicodedata
						try:
							value = str(field)
						except:
							try:
								value = str(field).encode("utf8", "replace") + " (decoded unicode)"
							except:
								value = "Unreadable (data)"
					
						#maybe an image?
						if (fieldsNames[columnIndex] == "data"):
							dataMagic = magic.whatis(value)

							if (dataMagic.partition("/")[0] == "image"):			
							
								#im = Image.open(StringIO.StringIO(value))
								#tkim = ImageTk.PhotoImage(im)
								#photoImages.append(tkim)
								#maintext("\n ")
								#textarea.image_create(END, image=tkim)
								
								qba = QtCore.QByteArray()
								qba.append(value)
								qimg = QtGui.QImage.fromData(qba)
								qpix = QtGui.QPixmap.fromImage(qimg)
								qicon = QtGui.QIcon(qpix)								
								
								newItem = QtGui.QTableWidgetItem(dataMagic)
								newItem.setIcon(qicon)
								
								self.ui.tableContent.setRowHeight(rowIndex, 100)
								self.ui.tableContent.setIconSize(QtCore.QSize(100,100))
								
							else:	
								text = self.dump(value, 16, 1000)
								newItem = QtGui.QTableWidgetItem(text)					
					
						# not data => text
						else:					
							newItem = QtGui.QTableWidgetItem(value)
						
						self.ui.tableContent.setItem(rowIndex, columnIndex, newItem)
						
						columnIndex = columnIndex + 1						
					
					rowIndex = rowIndex + 1
					
			except:
				print("Unexpected error:", sys.exc_info())
			
			seltabledb.close()
			self.ui.tableContent.resizeColumnsToContents()	
		
		
		

class IPBA2(QtGui.QMainWindow):

	def __init__(self, parent = None):
		QtGui.QMainWindow.__init__(self, parent)
		
		self.ui = Ui_MainWindow()
		self.ui.setupUi(self)
		
		self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
		
		self.parent = parent
		
		self.readBackupArchive()
		
		QtCore.QObject.connect(self.ui.fileTree, QtCore.SIGNAL("itemSelectionChanged()"), self.onTreeClick)
		QtCore.QObject.connect(self.ui.open_sqlite, QtCore.SIGNAL("clicked()"), self.openFile)
		
		self.ui.fileTree.setColumnWidth(0,200)
		self.ui.fileTree.setColumnWidth(2,16)
		
		self.ui.fileTree.setColumnHidden(1,True)
		self.ui.fileTree.setColumnHidden(3,True)
		
		# attach context menu to rightclick on elements tree
		self.ui.fileTree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.connect(self.ui.fileTree, QtCore.SIGNAL('customContextMenuRequested(QPoint)'), self.ctxMenu)	

	# builds context menu
	def ctxMenu(self, pos):

		data = self.getSelectedFileData()
		if (data == None): return
		
		realFileName = os.path.join(self.backup_path, data['fileid'])
		filemagic = self.readMagic(realFileName)
		
		showMenu = False
		
		menu =  QtGui.QMenu();
		
		# if sqlite
		if (filemagic.partition("/")[2] == "sqlite"):
			action1 = QtGui.QAction("Open with SQLite Browser", self)
			action1.triggered.connect(self.openSelectedSqlite)
			menu.addAction(action1)
			showMenu = True

		# if image
		if (filemagic.partition("/")[0] == "image"):
			action1 = QtGui.QAction("Open with Image Viewer", self)
			action1.triggered.connect(self.openSelectedImage)
			menu.addAction(action1)
			showMenu = True
	
		# if HEX (in any case)
		if True:
			action1 = QtGui.QAction("Open with Hex Viewer", self)
			action1.triggered.connect(self.openSelectedHex)
			menu.addAction(action1)
			showMenu = True
		
		if (showMenu):
			menu.exec_(self.ui.fileTree.mapToGlobal(pos));
	
	# CONTEXT MENU ACTIONS --------------------------------------------------------------------------
	
	def openSelectedSqlite(self):
		
		element = self.getSelectedFileData()
		if (element == None): return
		
		realFileName = os.path.join(self.backup_path, element['fileid'])
	
		newWidget = SqliteWidget(realFileName)
		newWidget.setTitle(element['file_name'] + " - SQLite Browser")
		self.ui.mdiArea.addSubWindow(newWidget)
		newWidget.show()

	def openSelectedImage(self):
		
		element = self.getSelectedFileData()
		if (element == None): return
		
		realFileName = os.path.join(self.backup_path, element['fileid'])
	
		newWidget = ImageWidget(realFileName)
		newWidget.setTitle(element['file_name'] + " - Image Viewer")
		self.ui.mdiArea.addSubWindow(newWidget)
		newWidget.show()	

	def openSelectedHex(self):
		
		element = self.getSelectedFileData()
		if (element == None): return
		
		realFileName = os.path.join(self.backup_path, element['fileid'])
	
		newWidget = HexWidget(realFileName)
		newWidget.setTitle(element['file_name'] + " - Image Viewer")
		self.ui.mdiArea.addSubWindow(newWidget)
		newWidget.show()
	
	#-----------------------------------------------------------------------------------------------
	
	# return database ID of the currently selected element
	def getSelectedElementID(self):
		currentSelectedElement = self.ui.fileTree.currentItem()
		if (currentSelectedElement): pass
		else: return None
		
		return currentSelectedElement.text(3)
		
	
	# return DB record for selected item
	def getSelectedElementData(self):
	
		currentSelectedElement = self.ui.fileTree.currentItem()
		if (currentSelectedElement): pass
		else: return None,None
		
		item_id = currentSelectedElement.text(3)
	
		data = self.getElementFromID(item_id)
		if (data == None): return None,None

		item_type = currentSelectedElement.text(1)
		
		return data, item_type			
	
	
	# return DB record for selected item (only files "-")
	def getSelectedFileData(self):
		data, item_type = self.getSelectedElementData()
		if (data == None): return None
		if (item_type != '-'): return None
		return data
	
	
	FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
	def hex2nums(self, src, length=8):
		N=0; result=''
		while src:
		   s,src = src[:length],src[length:]
		   hexa = ' '.join(["%02X"%ord(x) for x in s])
		   s = s.translate(self.FILTER)
		   N+=length
		   result += (hexa + " ")
		return result	


	def getElementFromID(self, id):
		query = "SELECT * FROM indice WHERE id = ?"
		self.cursor.execute(query, (id,))
		data = self.cursor.fetchone()
		
		if (data == None): return None
		
		if (len(data) == 0): 
			return None
		else:
			return data

	def readMagic(self, item_realpath):

		# check for existence 
		if (os.path.exists(item_realpath) == 0):
			return None
		
		# print file type (from magic numbers)
		filemagic = magic.file(item_realpath)
		return filemagic


	def openFile(self):

		element = self.getSelectedFileData()
		if (element == None): return
		
		realFileName = os.path.join(self.backup_path, element['fileid'])
		filemagic = self.readMagic(realFileName)
		
		# if sqlite file
		if (filemagic.partition("/")[2] == "sqlite"):
			newWidget = SqliteWidget(realFileName)
			newWidget.setTitle(element['file_name'] + " - SQLite Browser")
			self.ui.mdiArea.addSubWindow(newWidget)
			newWidget.show()
		
		# if graphics file
		elif (filemagic.partition("/")[0] == "image"):
			newWidget = ImageWidget(realFileName)
			newWidget.setTitle(element['file_name'] + " - Image Viewer")
			self.ui.mdiArea.addSubWindow(newWidget)
			newWidget.show()	
		
	
	def onTreeClick(self):
	
		data, item_type = self.getSelectedElementData()
		item_id = self.getSelectedElementID()
		if (data == None or item_id == None): return
		if (item_type != "-"): return
		
		item_name = str(data['file_name'])
		item_permissions = str(data['permissions'])
		item_userid = str(data['userid'])
		item_groupid = str(data['groupid'])
		item_mtime = str(datetime.datetime.fromtimestamp(int(data['mtime'])))
		item_atime = str(datetime.datetime.fromtimestamp(int(data['atime'])))
		item_ctime = str(datetime.datetime.fromtimestamp(int(data['ctime'])))
		item_filecode = str(data['fileid'])
		item_link_target = str(data['link_target'])
		item_datahash = str(data['datahash'])
		item_flag = str(data['flag'])
		
		self.ui.fileInfoText.clear()
		
		self.ui.fileInfoText.append("<strong>File</strong>: " + item_name)
		self.ui.fileInfoText.append("")		
		self.ui.fileInfoText.append("<strong>Element type</strong>: " + item_type)
		self.ui.fileInfoText.append("<strong>Permissions</strong>: " + item_permissions)
		self.ui.fileInfoText.append("<strong>Data hash</strong>: " + item_datahash)
		self.ui.fileInfoText.append("<strong>User id</strong>: " + item_userid)
		self.ui.fileInfoText.append("<strong>Group id</strong>: " + item_groupid)
		self.ui.fileInfoText.append("<strong>Last modify time</strong>: " + item_mtime)
		self.ui.fileInfoText.append("<strong>Last access Time</strong>: " + item_atime)
		self.ui.fileInfoText.append("<strong>Creation time</strong>: " + item_ctime)
		self.ui.fileInfoText.append("<strong>File Key (obfuscated file name)</strong>: " + item_filecode)
		self.ui.fileInfoText.append("<strong>Flag</strong>: " + item_flag)

		# file properties (from properties table, which is data from mbdb file)
		query = "SELECT property_name, property_val FROM properties WHERE file_id = %s" % item_id
		self.cursor.execute(query)
		data = self.cursor.fetchall()
		if (len(data) > 0):
			self.ui.fileInfoText.append("")
			self.ui.fileInfoText.append("<strong>Element properties (from mdbd file)</strong>:")
			for element in data:
				self.ui.fileInfoText.append("%s: %s" %(element[0], element[1]))

		# cursor back at top left
		textCursor = self.ui.fileInfoText.textCursor() 
		textCursor.setPosition(0) 
		self.ui.fileInfoText.setTextCursor(textCursor) 		
	
	def readBackupArchive(self):

		self.backup_path = "c:\Users\mario\AppData\Roaming\Apple Computer\MobileSync\Backup\\281fdc7a0d7d39e71bb8d7113f73acd97b88a751"
		
		#self.backup_path = QtGui.QFileDialog.getExistingDirectory(self, "Open Directory", "", QtGui.QFileDialog.ShowDirsOnly | QtGui.QFileDialog.DontResolveSymlinks);
		
		if (self.backup_path == None):
			sys.exit(0)
		
		self.backup_path = os.path.abspath(self.backup_path)

		# if exists Manifest.mbdx, then iOS <= 4
		iOSVersion = 5
		mbdxPath = os.path.join(self.backup_path, "Manifest.mbdx")
		if (os.path.exists(mbdxPath)):
			iOSVersion = 4
		
		# decode Manifest files
		mbdbPath = os.path.join(self.backup_path, "Manifest.mbdb")
		if (os.path.exists(mbdbPath)):
			mbdb = mbdbdecoding.process_mbdb_file(mbdbPath)
		else:
			#usage()
			print("\nManifest.mbdb not found in path \"%s\". Are you sure this is a correct iOS backup dir?\n"%(self.backup_path))
			sys.exit(1)
		
		# decode mbdx file (only iOS 4)
		if (iOSVersion == 4):
			mbdxPath = os.path.join(self.backup_path, "Manifest.mbdx")
			if (os.path.exists(mbdxPath)):
				mbdx = mbdbdecoding.process_mbdx_file(mbdxPath)
			else:
				#usage()
				print("\nManifest.mbdx not found in path \"%s\". Are you sure this is a correct iOS backup dir, and are you sure this is an iOS 4 backup?\n"%(self.backup_path))
				sys.exit(1)	

		# prepares DB
		database = sqlite3.connect(':memory:') # Create a database file in memory
		database.row_factory = sqlite3.Row
		self.cursor = database.cursor() # Create a cursor
		
		self.cursor.execute(
			"CREATE TABLE indice (" + 
			"id INTEGER PRIMARY KEY AUTOINCREMENT," +
			"type VARCHAR(1)," +
			"permissions VARCHAR(9)," +
			"userid VARCHAR(8)," +
			"groupid VARCHAR(8)," +
			"filelen INT," +
			"mtime INT," +
			"atime INT," +
			"ctime INT," +
			"fileid VARCHAR(50)," +
			"domain_type VARCHAR(100)," +
			"domain VARCHAR(100)," +
			"file_path VARCHAR(100)," +
			"file_name VARCHAR(100)," + 
			"link_target VARCHAR(100)," + 
			"datahash VARCHAR(100)," + 
			"flag VARCHAR(100)"
			");"
		)
		
		self.cursor.execute(
			"CREATE TABLE properties (" + 
			"id INTEGER PRIMARY KEY AUTOINCREMENT," +
			"file_id INTEGER," +
			"property_name VARCHAR(100)," +
			"property_val VARCHAR(100)" +
			");"
		)
			
		# count items parsed from Manifest file
		items = 0;
		
		# populates database by parsing manifest file
		for offset, fileinfo in mbdb.items():
			
			# iOS 4 (get file ID from mbdx file)
			if (iOSVersion == 4):
			
				if offset in mbdx:
					fileinfo['fileID'] = mbdx[offset]
				else:
					fileinfo['fileID'] = "<nofileID>"
					print >> sys.stderr, "No fileID found for %s" % fileinfo_str(fileinfo)
			
			# iOS 5 (no MBDX file, use SHA1 of complete file name)
			elif (iOSVersion == 5):
				fileID = hashlib.sha1()
				fileID.update("%s-%s"%(fileinfo['domain'], fileinfo['filename']) )
				fileinfo['fileID'] = fileID.hexdigest()	
		
			# decoding element type (symlink, file, directory)
			if (fileinfo['mode'] & 0xE000) == 0xA000: obj_type = 'l' # symlink
			elif (fileinfo['mode'] & 0xE000) == 0x8000: obj_type = '-' # file
			elif (fileinfo['mode'] & 0xE000) == 0x4000: obj_type = 'd' # dir
			
			# separates domain type (AppDomain, HomeDomain, ...) from domain name
			[domaintype, sep, domain] = fileinfo['domain'].partition('-');
			
			# separates file name from file path
			[filepath, sep, filename] = fileinfo['filename'].rpartition('/')
			if (type == 'd'):
				filepath = fileinfo['filename']
				filename = "";

			# Insert record in database
			query = "INSERT INTO indice(type, permissions, userid, groupid, filelen, mtime, atime, ctime, fileid, domain_type, domain, file_path, file_name, link_target, datahash, flag) VALUES(";
			query += "'%s'," 	% obj_type
			query += "'%s'," 	% mbdbdecoding.modestr(fileinfo['mode']&0x0FFF)
			query += "'%08x'," 	% fileinfo['userid']
			query += "'%08x'," 	% fileinfo['groupid']
			query += "%i," 		% fileinfo['filelen']
			query += "%i," 		% fileinfo['mtime']
			query += "%i," 		% fileinfo['atime']
			query += "%i," 		% fileinfo['ctime']
			query += "'%s'," 	% fileinfo['fileID']
			query += "'%s'," 	% domaintype.replace("'", "''")
			query += "'%s'," 	% domain.replace("'", "''")
			query += "'%s'," 	% filepath.replace("'", "''")
			query += "'%s'," 	% filename.replace("'", "''")
			query += "'%s'," 	% fileinfo['linktarget']
			query += "'%s'," 	% self.hex2nums(fileinfo['datahash']).replace("'", "''")
			query += "'%s'" 	% fileinfo['flag']
			query += ");"
			self.cursor.execute(query)
			
			items += 1;
			
			# check if file has properties to store in the properties table
			if (fileinfo['numprops'] > 0):
		
				query = "SELECT id FROM indice WHERE "
				query += "domain = '%s' " % domain.replace("'", "''")
				query += "AND fileid = '%s' " % fileinfo['fileID']
				query += "LIMIT 1"
				 
				self.cursor.execute(query);
				id = self.cursor.fetchall()
				
				if (len(id) > 0):
					index = id[0][0]
					properties = fileinfo['properties']
					for property in properties.keys():
						query = "INSERT INTO properties(file_id, property_name, property_val) VALUES (";
						query += "'%i'," % index
						query += "'%s'," % property
						query += "'%s'" % self.hex2nums(properties[property]).replace("'", "''")
						query += ");"
						
						self.cursor.execute(query);
			
				#print("File: %s, properties: %i"%(domain + ":" + filepath + "/" + filename, fileinfo['numprops']))
				#print(fileinfo['properties'])

		database.commit() 
		
		# print banner
		print("\nWorking directory: %s"%self.backup_path)
		print("Read elements: %i" %items)

		# retrieve domain families
		self.cursor.execute("SELECT DISTINCT(domain_type) FROM indice");
		domain_types = self.cursor.fetchall()
		
		for domain_type_u in domain_types:
			
			domain_type = str(domain_type_u[0])
			
			newDomainFamily = QtGui.QTreeWidgetItem(None)
			newDomainFamily.setText(0, domain_type)
			
			self.ui.fileTree.addTopLevelItem(newDomainFamily)
			
			# retrieve domains for the selected family
			query = "SELECT DISTINCT(domain) FROM indice WHERE domain_type = \"%s\" ORDER BY domain" % domain_type
			self.cursor.execute(query);
			domain_names = self.cursor.fetchall()
			
			for domain_name_u in domain_names:
				domain_name = str(domain_name_u[0])			
				
				newDomain = QtGui.QTreeWidgetItem(newDomainFamily)
				newDomain.setText(0, domain_name)
				
				if (len(domain_names) > 1):
					self.ui.fileTree.addTopLevelItem(newDomain)
			
				# retrieve paths for selected domain
				query = "SELECT DISTINCT(file_path) FROM indice WHERE domain_type = \"%s\" AND domain = \"%s\" ORDER BY file_path" %(domain_type, domain_name)
				self.cursor.execute(query)
				paths = self.cursor.fetchall()
				
				for path_u in paths:
					path = str(path_u[0])
					
					if (len(domain_names) > 1):
						newPath = QtGui.QTreeWidgetItem(newDomain)
					else:
						newPath = QtGui.QTreeWidgetItem(newDomainFamily)
					
					newPath.setText(0, path)
					self.ui.fileTree.addTopLevelItem(newPath)
					
					# retrieve files for selected path
					query = "SELECT file_name, filelen, id, type FROM indice WHERE domain_type = \"%s\" AND domain = \"%s\" AND file_path = \"%s\" ORDER BY file_name" %(domain_type, domain_name, path)
					self.cursor.execute(query)
					files = self.cursor.fetchall()
					
					for file in files:
						file_name = str(file[0].encode("utf-8"))
						if (file[1]) < 1024:
							file_dim = str(file[1]) + " b"
						else:
							file_dim = str(file[1] / 1024) + " kb"
						file_id = int(file[2])
						file_type = str(file[3])

						newFile = QtGui.QTreeWidgetItem(newPath)
						newFile.setText(0, file_name)
						newFile.setToolTip(0, file_name)
						newFile.setText(1, file_type)
						newFile.setText(2, str(file_dim))
						newFile.setText(3, str(file_id))
						self.ui.fileTree.addTopLevelItem(newFile)

		
		deviceinfo = plistutils.deviceInfo(os.path.join(self.backup_path, "Info.plist"))
		for element in deviceinfo.keys():
			self.ui.backupInfoText.append("<strong>%s</strong>: %s"%(element, deviceinfo[element]))
		
		textCursor = self.ui.backupInfoText.textCursor() 
		textCursor.setPosition(0) 
		self.ui.backupInfoText.setTextCursor(textCursor) 


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    main_ipba2_window = IPBA2()
    main_ipba2_window.show()
    sys.exit(app.exec_())