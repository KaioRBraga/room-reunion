import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class MeetingSummary {
  final int id;
  final String title;
  final String organizer;
  final DateTime start;
  final DateTime end;
  final bool checkedIn;
  final bool isPast;
  final String? virtualRoomUrl;

  MeetingSummary({
    required this.id,
    required this.title,
    required this.organizer,
    required this.start,
    required this.end,
    required this.checkedIn,
    required this.isPast,
    this.virtualRoomUrl,
  });

  factory MeetingSummary.fromJson(Map<String, dynamic> json) {
    final virtualRoomUrl = json['virtual_room_url'] as String?;
    return MeetingSummary(
      id: json['id'] as int,
      title: json['title'] as String,
      organizer: json['organizer'] as String,
      start: DateTime.parse(json['start'] as String),
      end: DateTime.parse(json['end'] as String),
      checkedIn: json['checked_in'] as bool? ?? false,
      isPast: json['is_past'] as bool? ?? false,
      virtualRoomUrl: (virtualRoomUrl != null && virtualRoomUrl.isNotEmpty) ? virtualRoomUrl : null,
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
      // Salas cadastradas antes do checklist podem ter o texto separado por
      // quebra de linha em vez de vírgula (era um textarea) - aceita os dois.
      list.addAll(
        notes.split(RegExp(r'[,\n]')).map((e) => e.trim()).where((e) => e.isNotEmpty),
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

/// Aparência do painel configurada pelo admin no site (aba "Layout do
/// painel"). Vem junto do status pra não precisar de uma chamada extra -
/// os defaults espelham `AppColors` e cobrem o caso de um servidor antigo
/// que ainda não manda essa chave.
/// Posição da agenda do dia em relação à faixa de status.
enum AgendaPosition { belowStatus, aboveStatus }

/// Posição do botão de ação principal: embutido na faixa de status (padrão)
/// ou isolado no canto superior direito (arranjo original, anterior aos
/// ajustes de design feitos a pedido do usuário).
enum ButtonPosition { statusBanner, topRight }

AgendaPosition _parseAgendaPosition(String? value) {
  return value == 'above_status' ? AgendaPosition.aboveStatus : AgendaPosition.belowStatus;
}

ButtonPosition _parseButtonPosition(String? value) {
  return value == 'top_right' ? ButtonPosition.topRight : ButtonPosition.statusBanner;
}

class DisplayLayoutSettings {
  final bool showLogo;
  final bool showTags;
  final bool showVideoIcon;
  final bool showScheduleHint;
  final Color colorAvailable;
  final Color colorStartingSoon;
  final Color colorInUse;
  final AgendaPosition agendaPosition;
  final ButtonPosition buttonPosition;
  final String? logoUrl;

  const DisplayLayoutSettings({
    required this.showLogo,
    required this.showTags,
    required this.showVideoIcon,
    required this.showScheduleHint,
    required this.colorAvailable,
    required this.colorStartingSoon,
    required this.colorInUse,
    this.agendaPosition = AgendaPosition.belowStatus,
    this.buttonPosition = ButtonPosition.statusBanner,
    this.logoUrl,
  });

  static const defaults = DisplayLayoutSettings(
    showLogo: true,
    showTags: true,
    showVideoIcon: true,
    showScheduleHint: true,
    colorAvailable: AppColors.available,
    colorStartingSoon: AppColors.startingSoon,
    colorInUse: AppColors.inUse,
  );

  factory DisplayLayoutSettings.fromJson(Map<String, dynamic>? json) {
    if (json == null) return defaults;
    final colors = json['colors'] as Map<String, dynamic>? ?? const {};
    return DisplayLayoutSettings(
      showLogo: json['show_logo'] as bool? ?? true,
      showTags: json['show_tags'] as bool? ?? true,
      showVideoIcon: json['show_video_icon'] as bool? ?? true,
      showScheduleHint: json['show_schedule_hint'] as bool? ?? true,
      colorAvailable: _parseColor(colors['available'], AppColors.available),
      colorStartingSoon: _parseColor(colors['starting_soon'], AppColors.startingSoon),
      colorInUse: _parseColor(colors['in_use'], AppColors.inUse),
      agendaPosition: _parseAgendaPosition(json['agenda_position'] as String?),
      buttonPosition: _parseButtonPosition(json['button_position'] as String?),
      logoUrl: json['logo_url'] as String?,
    );
  }

  static Color _parseColor(dynamic hex, Color fallback) {
    if (hex is! String) return fallback;
    final parsed = int.tryParse(hex.replaceFirst('#', ''), radix: 16);
    return parsed == null ? fallback : Color(0xFF000000 | parsed);
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
  final DisplayLayoutSettings layout;

  DisplayStatus({
    required this.room,
    required this.status,
    required this.currentMeeting,
    required this.nextMeeting,
    required this.checkInDeadline,
    required this.todaySchedule,
    required this.serverTime,
    this.layout = DisplayLayoutSettings.defaults,
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
      layout: DisplayLayoutSettings.fromJson(json['layout'] as Map<String, dynamic>?),
    );
  }
}
