from Timeline.Server.Constants import TIMELINE_LOGGER, LOGIN_SERVER, WORLD_SERVER, SERVER_ONLY_STAMP_GROUP
from Timeline import Username, Password, Inventory
from Timeline.Utils.Events import Event, PacketEventHandler, GeneralEvent
from Timeline.Database.DB import Penguin

from twisted.internet.defer import inlineCallbacks, returnValue

from collections import deque
import logging
from time import time

'''
AS2 and AS3 Compatible
'''
@PacketEventHandler.onXT('s', 'st#gsbcd', WORLD_SERVER)
@PacketEventHandler.onXT_AS2('s', 'st#gsbcd', WORLD_SERVER)
@inlineCallbacks
def handleGetSBCoverDetails(client, _id):
	peng = yield Penguin.find(_id)
	if peng is None:
		returnValue(client.send('gsbcd', '', '', '', '', '', ''))

	cover = str(peng.cover)
	if cover == '':
		cover = peng.cover = '1|0|0|0'
		peng.save()

	cover_details = cover.split('%')

	cover_properties = cover_details[0].split('|')
	colourID, highlightID, patternID, claspIconArtID = map(lambda x: int(x) if x != '' else 0, cover_properties)
	rest = cover_details[1:]
	client.send('gsbcd', colourID, highlightID, patternID, claspIconArtID, *rest)

'''
AS2 and AS3 Compatible
'''
@PacketEventHandler.onXT('s', 'st#gps', WORLD_SERVER)
@PacketEventHandler.onXT_AS2('s', 'st#gps', WORLD_SERVER)
@inlineCallbacks
def handleGetPlayerStamps(client, _id):
	peng = yield Penguin.find(_id)
	if peng is None:
		returnValue(client.send('gps', _id, ''))

	stamps = str(peng.stamps)
	if stamps == '':
		client.send('gps', _id, '')

	client.send('gps', _id, '|'.join(map(lambda x: x.split(',')[0], stamps.split("|"))))

'''
AS2 and AS3 Compatible
'''
@PacketEventHandler.onXT('s', 'st#gmres', WORLD_SERVER, p_r = False)
@PacketEventHandler.onXT_AS2('s', 'st#gmres', WORLD_SERVER, p_r = False)
def handleGetRecentStamps(client, data):
	client.send('gmres', '|'.join(map(str, client['recentStamps'])))
	client.penguin.recentStamps = list()

'''
AS2 and AS3 Compatible
'''
@PacketEventHandler.onXT('s', 'st#ssbcd', WORLD_SERVER)
@PacketEventHandler.onXT_AS2('s', 'st#ssbcd', WORLD_SERVER)
def handleSBCoverUpdate(client, color, highlight, pattern, icon, stamps):
	coverCrumb = client.engine.stampCrumbs.cover

	if not client['member']:
		return client.send('e', 999)

	if not color in coverCrumb['colors'] or not highlight in coverCrumb['highlights'] or not pattern in coverCrumb['patterns'] or not icon in coverCrumb['icons']:
		return

	stamp_string = ['|'.join(map(str, [color, highlight, pattern, icon]))]
	stamps_used = list()

	for stamp in stamps:
		item_type, item_id, x, y, rotation, depth = stamp
		#check for item_type: currently not sure of exact values it can hold

		#check if item is a stamp
		stamp = client.engine.stampCrumbs[item_id]
		if stamp is None:
			#check if it's a pin and in inventory
			item = client.engine.itemCrumbs[item_id]
			if item is None:
				return # doesn't exists at all!

			if not(item.type == 8 and item in client['inventory']): #pin
				return
			
			stamp = item
		else:
			#checl for stamp earned?
			if stamp not in client['stampHandler']:
				return

		if item_id in stamps_used:
			return # oops!

		stamps_used.append(item_id)

		stamp_string.append('|'.join(map(str, [item_type, int(stamp), x, y, rotation, depth])))

	client.dbpenguin.cover = '%'.join(stamp_string)
	client.dbpenguin.save()

	client.send('ssbcd', 'success')

'''
AS2 and AS3 Compatible
'''
@PacketEventHandler.onXT('s', 'st#sse', WORLD_SERVER)
@PacketEventHandler.onXT_AS2('s', 'st#sse', WORLD_SERVER)
def handleStampEarned(client, _id, fromServer = False):
	stamp = client.engine.stampCrumbs[_id]
	if stamp is None:
		return

	if stamp.group in SERVER_ONLY_STAMP_GROUP and not fromServer:
		client.engine.log("warn", client['username'], "trying to manipulate Stamp System.")
		# ban?
		return

	if stamp in client['stampHandler']:
		return # lol

	#You earned a stamp, earn a penny now B-)
	client['coins'] += 1
	client['stampHandler'].append(stamp)

	stamps = str(client.dbpenguin.stamps).split('|') if client.dbpenguin.stamps != '' else list()
	stamps.append('{},{}'.format(int(stamp), int(time())))

	client.dbpenguin.stamps = '|'.join(stamps)
	client.dbpenguin.save()

	client.penguin.recentStamps.append(stamp)

	client.send('aabs', int(stamp))

'''
Handler to award user stamp, if he's in same room as a mascot. 
'''
@GeneralEvent.on("mascot-joined-room")
def handleAwardMascotStamp(room, mascot_name, penguins):
	availableMascotStamps = room.roomHandler.engine.stampCrumbs.getStampsByGroup(6)
	mascotStamps = {str(stamp.name).strip():stamp.id for stamp in availableMascotStamps}
	mascotToSearch = str(mascot_name).strip()

	if mascotToSearch in mascotStamps:
		stampId = mascotStamps[mascotToSearch]
		[handleStampEarned(client, stampId, True) for client in penguins]