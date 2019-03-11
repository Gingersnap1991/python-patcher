#!/bin/bash
bold=$(tput bold)
normal=$(tput sgr0)

## DEPENDENCY CHECKS ##
# command -v dialog >/dev/null 2>&1 || { echo >&2 "I require the dialog package to be installed in order to display menus. Please install this package first."; exit 1; }
command -v 7z >/dev/null 2>&1 || { echo >&2 "I require the p7zip package to be installed in order to display menus. Please install this package first."; exit 1; }


## DEFAULT PATHS ##
onikakushipath="$HOME/.local/share/Steam/steamapps/common/Higurashi When They Cry/"
watanagashipath="$HOME/.local/share/Steam/steamapps/common/Higurashi 02 - Watanagashi"
tatarigoroshipath="$HOME/.local/share/Steam/steamapps/common/Higurashi 03 - Tatarigoroshi"
himatsubushipath="$HOME/.local/share/Steam/steamapps/common/Higurashi 04 - Himatsubushi"
meakashipath="$HOME/.local/share/Steam/steamapps/common/Higurashi When They Cry Hou - Ch. 5 Meakashi"
tsumiborohoshipath="$HOME/.local/share/Steam/steamapps/common/Higurashi When They Cry Hou - Ch.6 Tsumihoroboshi"


## MENU FUNCTIONS ##
#welcomemsg(){
#	dialog --title "07th Mod Unofficial Installer for POSIX" \
#		--msgbox "Welcome to the Installer!\\n\\nThis Script will allow you to install/update your 07th games. Please report any bugs!" 10 60
#       }

install() {
echo "The Current Installation Location is:" $path
read -p "Press [ENTER] to install to this location or enter another install location >>" userPath

# Assign Path if not Blank
if [[ -n "$userPath" ]]; then
	path="$userPath"
fi

if [[ -e "$path" ]]; then
	echo "INSTALLING TO $path"
else
	echo "Cannot access path. Have you entered it correctly? Do you have permissions?"; install
fi

PATCHDIR=/tmp/07thinstaller-${game[0]}/
[ -d ${PATCHDIR} ] || mkdir ${PATCHDIR}
cd "$PATCHDIR"

echo "${bold}Downloading Assets${normal}"
for l in ${URL[@]}; do
	curl -O -J $l
done

echo "${bold}Downloading Latest Patch Release${normal}"
LATEST_RELEASE=$(curl -L -s -H 'Accept: application/json' https://github.com/07th-mod/$game/releases/latest)
LATEST_VERSION=$(echo $LATEST_RELEASE | sed -e 's/.*"tag_name":"\([^"]*\)".*/\1/')
ARTIFACT_URL="https://github.com/07th-mod/${game[0]}/releases/download/$LATEST_VERSION/${game[1]}.Voice.and.Graphics.Patch.$LATEST_VERSION.zip"
curl -L $ARTIFACT_URL -o patch.zip

# Begin Patching
for patch in *.7z; do
	7z x "$patch" -aoa -o"$path"
done
7z x patch.zip -aoa -o"$path"

displaydone
}


titleselect(){
	while true; do
		clear
		cat << _EOF_
Please Select a Game to Patch:

1. Higurashi no Naku Horo ni
2. Umineko no Naku Horo ni

_EOF_
read -p "Select Game >"
    case $REPLY in
      1)
	higuselect
	break
        ;;
      2)
	umiselect
	break
        ;;
      q)
	exit
        ;;
    esac
       done
}
higuselect(){
	while true; do
		clear
		cat << _EOF_
${bold}Please Select a Game to Patch:${normal}

-- Higurashi --

Chapter 1: Onikakushi
Chapter 2: Watanagashi
Chapter 3: Tatarigoroshi
Chapter 4: Himatsubushi
Chapter 5: Meakashi
Chapter 6: Tsumihoroboshi

_EOF_
read -p "Select Chapter [0-6] >"
    case $REPLY in
      1)
	path=$onikakushipath
	game=(onikakushi Onikakushi)
	options
        ;;
      2)
	path=$watanagashipath
	game=(watanagashi Watanagashi)
	options
        ;;
      3)
	path=$tatarigoroshipath
	game=(tatarigoroshi Tatarigoroshi)
	options
        ;;
      4)
	path=$himatsubushipath
	game=(himatsubushi Himatsubushi)
	options
        ;;
      5)
	path=$meakashipath
	game=(meakashi Meakashi)
	options
        ;;
      6)
	path=$tsumihoroboshipath
	game=(tsumihoroboshi Tsumihoroboshi)
	options
        ;;
      q)
	break
        ;;
    esac
       done
}

options(){

## ASSET URLS (NO PATCH) ##
URL_CG=https://07th-mod.com/rikachama/${game[1]}-CG.7z
URL_CGALT=https://07th-mod.com/rikachama/${game[1]}-CGAlt.7z
URL_VOICE=https://07th-mod.com/rikachama/${game[1]}-Voices.7z
URL_UI=https://07th-mod.com/rikachama/${game[1]}-UI_UNIX.7z
URL_MOVIE=https://07th-mod.com/rikachama/${game[1]}-Movie_UNIX.7z

	clear
	echo "Select Options for ${game[1]}"

	#Base-Patchset
	URL="$URL_CG $URL_VOICE $URL_MOVIE"

	read -p "Would you like to Enable support for Alternate Sprites? [y/N] >"
	if [[ "$REPLY" =~ ^[Yy]+$ ]]; then
		URL="$URL $URL_CGALT"
	fi

	read -p "Would you like to Enable the Updated UI (Recommended)? [Y/n] >"
	if [[ "$REPLY" != ^[Nn]+$ ]]; then
		if [[ "${game[0]}" =~ tatarigoroshi ]]; then
			read -p "Is your Tatarigoroshi the Steam Release? [Y/n] >" STEAM
			if [[ "$STEAM" =~ ^[Nn]+$ ]]; then
				URL="$URL https://07th-mod.com/rikachama/Tatarigoroshi-UI_UNIX-MG.7z"
			else
				URL="$URL https://07th-mod.com/rikachama/Tatarigoroshi-UI_UNIX.7z"
			fi
		else
			URL="$URL $URL_UI"
		fi
	fi
	install
}

displaydone(){
	echo "Patch Installation is Complete."
	read -p "Would you like to Patch another Chapter? [y/N] >"
	if [[ "$REPLY" =~ ^[Yy]+$ ]]; then
		higuselect
	fi
	exit $?
}

## BOOTSTRAP ## (UNDER CONSTRUCTION)
#welcomemsg
higuselect
exit $?
