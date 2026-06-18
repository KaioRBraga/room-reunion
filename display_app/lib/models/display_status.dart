class MeetingSummary {
  final int id;
  final String title;
  final String organizer;
  final DateTime start;
  final DateTime end;
  final bool checkedIn;
  final bool isPast;

  MeetingSummary({
    required this.id,
    required this.title,
    required this.organizer,
    required this.start,
    required this.end,
    required this.checkedIn,
    required this.isPast,
  });

  factory MeetingSummary.fromJson(Map<String, dynamic> json) {
    return MeetingSummary(
      id: json['id'] as int,
      title: json['title'] as String,
      organizer: json['organizer'] as String,
      start: DateTime.parse(json['start'] as String),
      end: DateTime.parse(json['end'] as String),
      checkedIn: json['checked_in'] as bool? ?? false,
      isPast: json['is_past'] as bool? ?? false,
    );
  }
}

class RoomInfo {
  final int id;
  final String name;
  final int capacity;
  final String? location;
  final String? equipmentNotes;

  RoomInfo({
    required this.id,
    required this.name,
    required this.capacity,
    this.location,
    this.equipmentNotes,
  });

  factory RoomInfo.fromJson(Map<String, dynamic> json) {
    return RoomInfo(
      id: json['id'] as int,
      name: json['name'] as String,
      capacity: json['capacity'] as int,
      location: json['location'] as String?,
      equipmentNotes: json['equipment_notes'] as String?,
    );
  }

  List<String> get tags {
    final list = <String>['$capacity pessoas'];
    final notes = equipmentNotes;
    if (notes != null && notes.trim().isNotEmpty) {
      list.addAll(
        notes.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty),
      );
    }
    return list;
  }
}

enum DisplayStatusKind { available, startingSoon, inUse }

DisplayStatusKind parseDisplayStatus(String value) {
  switch (value) {
    case 'starting_soon':
      return DisplayStatusKind.startingSoon;
    case 'in_use':
      return DisplayStatusKind.inUse;
    default:
      return DisplayStatusKind.available;
  }
}

class DisplayStatus {
  final RoomInfo room;
  final DisplayStatusKind status;
  final MeetingSummary? currentMeeting;
  final MeetingSummary? nextMeeting;
  final DateTime? checkInDeadline;
  final List<MeetingSummary> todaySchedule;
  final DateTime serverTime;

  DisplayStatus({
    required this.room,
    required this.status,
    required this.currentMeeting,
    required this.nextMeeting,
    required this.checkInDeadline,
    required this.todaySchedule,
    required this.serverTime,
  });

  factory DisplayStatus.fromJson(Map<String, dynamic> json) {
    return DisplayStatus(
      room: RoomInfo.fromJson(json['room'] as Map<String, dynamic>),
      status: parseDisplayStatus(json['status'] as String),
      currentMeeting: json['current_meeting'] != null
          ? MeetingSummary.fromJson(json['current_meeting'] as Map<String, dynamic>)
          : null,
      nextMeeting: json['next_meeting'] != null
          ? MeetingSummary.fromJson(json['next_meeting'] as Map<String, dynamic>)
          : null,
      checkInDeadline: json['check_in_deadline'] != null
          ? DateTime.parse(json['check_in_deadline'] as String)
          : null,
      todaySchedule: (json['today_schedule'] as List<dynamic>)
          .map((e) => MeetingSummary.fromJson(e as Map<String, dynamic>))
          .toList(),
      serverTime: DateTime.parse(json['server_time'] as String),
    );
  }
}
