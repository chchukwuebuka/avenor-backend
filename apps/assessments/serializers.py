from rest_framework import serializers
from .models import (
    Quiz,
    Question,
    QuestionOption,
    QuizAttempt,
    Assignment,
    AssignmentSubmission,
    Certificate,
)


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'order']


class QuestionOptionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'prompt', 'points', 'order', 'options']


class QuestionReviewSerializer(serializers.ModelSerializer):
    options = QuestionOptionReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'prompt', 'explanation', 'points', 'order', 'options']


class QuizListSerializer(serializers.ModelSerializer):
    questions_count = serializers.IntegerField(source='questions.count', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'title',
            'course_title',
            'description',
            'passing_score_percentage',
            'time_limit_minutes',
            'max_attempts',
            'questions_count',
            'order',
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'title',
            'course_title',
            'description',
            'passing_score_percentage',
            'time_limit_minutes',
            'max_attempts',
            'questions',
            'order',
        ]


class QuizSubmitSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    answers = serializers.DictField(
        child=serializers.CharField(),
        help_text='Mapping of question_id to selected option_id'
    )


class QuizAttemptSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    student_email = serializers.CharField(source='enrollment.student.email', read_only=True)
    questions = QuestionReviewSerializer(source='quiz.questions', many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id',
            'quiz_title',
            'student_email',
            'attempt_number',
            'score',
            'max_score',
            'score_percentage',
            'is_passed',
            'started_at',
            'completed_at',
            'answers_payload',
            'questions',
        ]
        read_only_fields = fields


class AssignmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'id',
            'title',
            'course_title',
            'prompt',
            'rubric_criteria',
            'max_points',
            'due_days_after_start',
        ]


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    student_email = serializers.CharField(source='enrollment.student.email', read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment',
            'assignment_title',
            'student_email',
            'submission_url',
            'notes',
            'submitted_at',
            'grade_points',
            'feedback',
            'graded_at',
        ]
        read_only_fields = ['id', 'submitted_at', 'grade_points', 'feedback', 'graded_at']


class AssignmentGradeSerializer(serializers.Serializer):
    grade_points = serializers.DecimalField(max_digits=5, decimal_places=2)
    feedback = serializers.CharField(required=False, default='')


class CertificateSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='tenant.name', read_only=True)
    institution_slug = serializers.CharField(source='tenant.slug', read_only=True)
    student_email = serializers.CharField(source='enrollment.student.email', read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_number',
            'verification_hash',
            'recipient_name',
            'student_email',
            'course_title',
            'grade',
            'institution_name',
            'institution_slug',
            'issued_at',
            'metadata',
        ]
        read_only_fields = fields


class CertificateVerifySerializer(serializers.Serializer):
    hash = serializers.CharField()
