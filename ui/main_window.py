<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <property name="geometry">
   <rect>
    <x>0</x>
    <y>0</y>
    <width>1064</width>
    <height>727</height>
   </rect>
  </property>
  <property name="windowTitle">
   <string>MainWindow</string>
  </property>
  <widget class="QWidget" name="centralwidget">
   <layout class="QVBoxLayout" name="verticalLayout_3">
    <item>
     <layout class="QGridLayout" name="gridLayout_3">
      <item row="0" column="0">
       <widget class="QCheckBox" name="show_tips_checkbox">
        <property name="text">
         <string/>
        </property>
        <property name="icon">
         <iconset theme="QIcon::ThemeIcon::HelpFaq"/>
        </property>
        <property name="checkable">
         <bool>true</bool>
        </property>
       </widget>
      </item>
      <item row="1" column="0">
       <widget class="QTabWidget" name="tabWidget">
        <property name="enabled">
         <bool>true</bool>
        </property>
        <property name="autoFillBackground">
         <bool>false</bool>
        </property>
        <property name="currentIndex">
         <number>0</number>
        </property>
        <property name="usesScrollButtons">
         <bool>false</bool>
        </property>
        <property name="documentMode">
         <bool>true</bool>
        </property>
        <property name="tabsClosable">
         <bool>false</bool>
        </property>
        <property name="movable">
         <bool>false</bool>
        </property>
        <widget class="QWidget" name="tab">
         <attribute name="title">
          <string>Transcription service</string>
         </attribute>
         <layout class="QGridLayout" name="gridLayout_2">
          <item row="0" column="0">
           <layout class="QVBoxLayout" name="verticalLayout_6">
            <item>
             <widget class="QGroupBox" name="Audio_file_frame">
              <property name="title">
               <string>&amp;Audio File(s)</string>
              </property>
              <layout class="QHBoxLayout" name="horizontalLayout_2">
               <item>
                <widget class="QLabel" name="label">
                 <property name="text">
                  <string>File Path(s):</string>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QLineEdit" name="audio_file_entry"/>
               </item>
               <item>
                <widget class="QPushButton" name="browse_button">
                 <property name="text">
                  <string/>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::DocumentOpen"/>
                 </property>
                </widget>
               </item>
              </layout>
             </widget>
            </item>
            <item>
             <widget class="QGroupBox" name="Processing_options_frame">
              <property name="enabled">
               <bool>true</bool>
              </property>
              <property name="title">
               <string>&amp;Processing Options</string>
              </property>
              <layout class="QVBoxLayout" name="verticalLayout_4">
               <item>
                <layout class="QGridLayout" name="gridLayout">
                 <item row="0" column="0">
                  <widget class="QGroupBox" name="Model_selection_frame">
                   <property name="title">
                    <string>&amp;Model selection</string>
                   </property>
                   <layout class="QHBoxLayout" name="horizontalLayout">
                    <item>
                     <widget class="QComboBox" name="model_dropdown"/>
                    </item>
                    <item>
                     <widget class="QLabel" name="model_description_label">
                      <property name="text">
                       <string>TextLabel</string>
                      </property>
                     </widget>
                    </item>
                   </layout>
                  </widget>
                 </item>
                 <item row="0" column="1">
                  <widget class="QGroupBox" name="Speaker_options_frame">
                   <property name="title">
                    <string>&amp;Speaker detection</string>
                   </property>
                   <layout class="QVBoxLayout" name="verticalLayout">
                    <item>
                     <widget class="QCheckBox" name="diarization_checkbutton">
                      <property name="text">
                       <string>Enable Speaker Diarization</string>
                      </property>
                     </widget>
                    </item>
                    <item>
                     <widget class="QCheckBox" name="auto_merge_checkbutton">
                      <property name="text">
                       <string>Automatically Merge</string>
                      </property>
                     </widget>
                    </item>
                   </layout>
                  </widget>
                 </item>
                 <item row="0" column="2">
                  <widget class="QGroupBox" name="Timestamps_options_frame">
                   <property name="title">
                    <string>&amp;Timestamps</string>
                   </property>
                   <layout class="QVBoxLayout" name="verticalLayout_2">
                    <item>
                     <widget class="QCheckBox" name="timestamps_checkbutton_2">
                      <property name="text">
                       <string>Include Timestamps</string>
                      </property>
                     </widget>
                    </item>
                    <item>
                     <widget class="QCheckBox" name="end_times_checkbutton">
                      <property name="text">
                       <string>Include End Times</string>
                      </property>
                     </widget>
                    </item>
                   </layout>
                  </widget>
                 </item>
                 <item row="1" column="0" colspan="3">
                  <widget class="QGroupBox" name="huggingface_token_frame">
                   <property name="title">
                    <string>&amp;Hugging Face Token</string>
                   </property>
                   <layout class="QHBoxLayout" name="horizontalLayout_3">
                    <item>
                     <widget class="QLabel" name="label_2">
                      <property name="text">
                       <string>Copy/Paste Token here:</string>
                      </property>
                     </widget>
                    </item>
                    <item>
                     <widget class="QLineEdit" name="huggingface_token_entry"/>
                    </item>
                    <item>
                     <widget class="QPushButton" name="save_token_button">
                      <property name="text">
                       <string>Save</string>
                      </property>
                      <property name="icon">
                       <iconset theme="QIcon::ThemeIcon::DocumentSave"/>
                      </property>
                     </widget>
                    </item>
                   </layout>
                  </widget>
                 </item>
                </layout>
               </item>
              </layout>
             </widget>
            </item>
            <item>
             <widget class="QGroupBox" name="status_and_play_frame">
              <property name="title">
               <string/>
              </property>
              <layout class="QVBoxLayout" name="verticalLayout_5">
               <item>
                <widget class="QLabel" name="status_label">
                 <property name="text">
                  <string>Status: inactive</string>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QProgressBar" name="progress_bar">
                 <property name="value">
                  <number>0</number>
                 </property>
                 <property name="invertedAppearance">
                  <bool>false</bool>
                 </property>
                 <property name="textDirection">
                  <enum>QProgressBar::Direction::TopToBottom</enum>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="start_processing_button">
                 <property name="text">
                  <string>Start Processing</string>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::MediaPlaybackStart"/>
                 </property>
                </widget>
               </item>
              </layout>
             </widget>
            </item>
            <item>
             <widget class="QGroupBox" name="Output_area_frame">
              <property name="title">
               <string>&amp;Output text area</string>
              </property>
              <layout class="QVBoxLayout" name="verticalLayout_8">
               <item>
                <widget class="QTextEdit" name="output_text_area"/>
               </item>
               <item>
                <widget class="QPushButton" name="correction_button">
                 <property name="text">
                  <string>Head to correction tab</string>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::GoNext"/>
                 </property>
                </widget>
               </item>
              </layout>
             </widget>
            </item>
           </layout>
          </item>
         </layout>
        </widget>
        <widget class="QWidget" name="tab_2">
         <attribute name="title">
          <string>Correction window</string>
         </attribute>
         <layout class="QVBoxLayout" name="verticalLayout_9">
          <item>
           <widget class="QGroupBox" name="Load_objects_frame">
            <property name="title">
             <string>Load Files</string>
            </property>
            <layout class="QGridLayout" name="gridLayout_4">
             <item row="0" column="1">
              <widget class="QLineEdit" name="correction_transcription_entry"/>
             </item>
             <item row="1" column="2">
              <widget class="QPushButton" name="correction_browse_audio_btn">
               <property name="text">
                <string/>
               </property>
               <property name="icon">
                <iconset theme="QIcon::ThemeIcon::DocumentOpen"/>
               </property>
              </widget>
             </item>
             <item row="0" column="0">
              <widget class="QLabel" name="label_3">
               <property name="text">
                <string>Transcription File:</string>
               </property>
              </widget>
             </item>
             <item row="0" column="2">
              <widget class="QPushButton" name="correction_browse_transcription_btn">
               <property name="text">
                <string/>
               </property>
               <property name="icon">
                <iconset theme="QIcon::ThemeIcon::DocumentOpen"/>
               </property>
              </widget>
             </item>
             <item row="1" column="0">
              <widget class="QLabel" name="label_4">
               <property name="text">
                <string>Audio File:</string>
               </property>
              </widget>
             </item>
             <item row="1" column="1">
              <widget class="QLineEdit" name="correction_audio_entry"/>
             </item>
             <item row="0" column="4" rowspan="2">
              <widget class="QPushButton" name="correction_save_changes_btn">
               <property name="text">
                <string>Save Changes</string>
               </property>
               <property name="icon">
                <iconset theme="QIcon::ThemeIcon::DocumentSave"/>
               </property>
              </widget>
             </item>
             <item row="0" column="3" rowspan="2">
              <widget class="QPushButton" name="correction_load_files_btn">
               <property name="text">
                <string>Load files</string>
               </property>
               <property name="icon">
                <iconset theme="QIcon::ThemeIcon::GoDown"/>
               </property>
              </widget>
             </item>
            </layout>
           </widget>
          </item>
          <item>
           <widget class="QGroupBox" name="Audio_player_frame">
            <property name="sizePolicy">
             <sizepolicy hsizetype="Preferred" vsizetype="Preferred">
              <horstretch>0</horstretch>
              <verstretch>0</verstretch>
             </sizepolicy>
            </property>
            <property name="title">
             <string>&amp;Audio player</string>
            </property>
            <layout class="QHBoxLayout" name="horizontalLayout_5">
             <item>
              <layout class="QHBoxLayout" name="horizontalLayout_4" stretch="0,0,0,0">
               <property name="spacing">
                <number>1</number>
               </property>
               <property name="sizeConstraint">
                <enum>QLayout::SizeConstraint::SetDefaultConstraint</enum>
               </property>
               <item>
                <widget class="QPushButton" name="correction_play_pause_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string>Play </string>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::MediaPlaybackStart"/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="correction_rewind_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string>5s</string>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::MediaSeekBackward"/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="correction_forward_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string>5s</string>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::MediaSeekForward"/>
                 </property>
                </widget>
               </item>
               <item>
                <spacer name="horizontalSpacer_2">
                 <property name="orientation">
                  <enum>Qt::Orientation::Horizontal</enum>
                 </property>
                 <property name="sizeType">
                  <enum>QSizePolicy::Policy::Fixed</enum>
                 </property>
                 <property name="sizeHint" stdset="0">
                  <size>
                   <width>10</width>
                   <height>20</height>
                  </size>
                 </property>
                </spacer>
               </item>
              </layout>
             </item>
             <item>
              <widget class="QWidget" name="correction_timeline_frame" native="true">
               <property name="sizePolicy">
                <sizepolicy hsizetype="Expanding" vsizetype="Preferred">
                 <horstretch>0</horstretch>
                 <verstretch>0</verstretch>
                </sizepolicy>
               </property>
               <property name="minimumSize">
                <size>
                 <width>300</width>
                 <height>0</height>
                </size>
               </property>
              </widget>
             </item>
             <item>
              <spacer name="horizontalSpacer_3">
               <property name="orientation">
                <enum>Qt::Orientation::Horizontal</enum>
               </property>
               <property name="sizeType">
                <enum>QSizePolicy::Policy::Fixed</enum>
               </property>
               <property name="sizeHint" stdset="0">
                <size>
                 <width>10</width>
                 <height>20</height>
                </size>
               </property>
              </spacer>
             </item>
             <item>
              <widget class="QLabel" name="correction_time_label">
               <property name="sizePolicy">
                <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                 <horstretch>0</horstretch>
                 <verstretch>0</verstretch>
                </sizepolicy>
               </property>
               <property name="minimumSize">
                <size>
                 <width>0</width>
                 <height>0</height>
                </size>
               </property>
               <property name="text">
                <string>00:00 / 00:00</string>
               </property>
              </widget>
             </item>
             <item>
              <widget class="QPushButton" name="save_timestamp_btn">
               <property name="sizePolicy">
                <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                 <horstretch>0</horstretch>
                 <verstretch>0</verstretch>
                </sizepolicy>
               </property>
               <property name="text">
                <string/>
               </property>
              </widget>
             </item>
            </layout>
           </widget>
          </item>
          <item>
           <widget class="QGroupBox" name="options_and_text_edit_frame">
            <property name="title">
             <string/>
            </property>
            <layout class="QVBoxLayout" name="verticalLayout_7">
             <item>
              <layout class="QHBoxLayout" name="horizontalLayout_6">
               <property name="sizeConstraint">
                <enum>QLayout::SizeConstraint::SetDefaultConstraint</enum>
               </property>
               <item>
                <widget class="QPushButton" name="Undo_button">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::EditUndo"/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="Redo_Button">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::EditRedo"/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="edit_speaker_btn">
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="correction_text_edit_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="correction_timestamp_edit_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="segment_btn">
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="merge_segments_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="delete_segment_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="correction_assign_speakers_btn">
                 <property name="enabled">
                  <bool>true</bool>
                 </property>
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                 <property name="icon">
                  <iconset theme="QIcon::ThemeIcon::ContactNew"/>
                 </property>
                </widget>
               </item>
               <item>
                <spacer name="horizontalSpacer">
                 <property name="orientation">
                  <enum>Qt::Orientation::Horizontal</enum>
                 </property>
                 <property name="sizeHint" stdset="0">
                  <size>
                   <width>40</width>
                   <height>20</height>
                  </size>
                 </property>
                </spacer>
               </item>
               <item>
                <widget class="QComboBox" name="text_font">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QComboBox" name="Police_size">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                </widget>
               </item>
               <item>
                <widget class="QPushButton" name="change_highlight_color_btn">
                 <property name="sizePolicy">
                  <sizepolicy hsizetype="Fixed" vsizetype="Fixed">
                   <horstretch>0</horstretch>
                   <verstretch>0</verstretch>
                  </sizepolicy>
                 </property>
                 <property name="text">
                  <string/>
                 </property>
                </widget>
               </item>
              </layout>
             </item>
             <item>
              <widget class="SelectableTextEdit" name="correction_text_area"/>
             </item>
            </layout>
           </widget>
          </item>
         </layout>
        </widget>
       </widget>
      </item>
     </layout>
    </item>
   </layout>
  </widget>
  <widget class="QStatusBar" name="statusbar"/>
 </widget>
 <customwidgets>
  <customwidget>
   <class>SelectableTextEdit</class>
   <extends>QTextEdit</extends>
   <header>ui.selectable_text_edit</header>
  </customwidget>
 </customwidgets>
 <resources/>
 <connections/>
</ui>
