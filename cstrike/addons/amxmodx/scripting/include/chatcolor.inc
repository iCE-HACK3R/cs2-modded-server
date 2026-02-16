/**
 * chatcolor.inc - Colored Chat Messages for AMX Mod X
 * Standard community include for colored chat in Counter-Strike 1.6
 * Based on work by Exolent[jNr] and Numb
 */

#if defined _chatcolor_included
	#endinput
#endif
#define _chatcolor_included

enum Color {
	Normal = 1,
	Green,
	TeamColor,
	Grey,
	Red,
	Blue,
}

new TeamName[][] = {
	"",
	"TERRORIST",
	"CT",
	"SPECTATOR"
}

stock ColorChat(id, Color:type, const msg[], any:...) {
	new message[256]

	switch(type) {
		case Normal:  message[0] = 0x01
		case Green:   message[0] = 0x04
		default:      message[0] = 0x03
	}

	vformat(message[1], 251, msg, 4)

	message[192] = '^0'

	new team, ColorChange, index, MSG_Type

	if(id) {
		MSG_Type = MSG_ONE
		index = id
	} else {
		index = FindPlayer()
		MSG_Type = MSG_ALL
	}

	if(!index)
		return

	team = get_user_team(index)

	ColorChange = ColorSelection(index, MSG_Type, type)

	ShowColorMessage(index, MSG_Type, message)

	if(ColorChange)
		Team_Info(index, MSG_Type, TeamName[team])
}

stock ShowColorMessage(id, type, message[]) {
	static msgSayText
	if(!msgSayText)
		msgSayText = get_user_msgid("SayText")

	message_begin(type, msgSayText, _, id)
	write_byte(id)
	write_string(message)
	message_end()
}

stock Team_Info(id, type, team[]) {
	static msgTeamInfo
	if(!msgTeamInfo)
		msgTeamInfo = get_user_msgid("TeamInfo")

	message_begin(type, msgTeamInfo, _, id)
	write_byte(id)
	write_string(team)
	message_end()
}

stock ColorSelection(index, type, Color:Type) {
	switch(Type) {
		case Red:       return Team_Info(index, type, TeamName[1])
		case Blue:      return Team_Info(index, type, TeamName[2])
		case Grey:      return Team_Info(index, type, TeamName[0])
	}

	return 0
}

stock FindPlayer() {
	new i = -1

	while(i <= get_maxplayers()) {
		if(is_user_connected(++i))
			return i
	}

	return -1
}
