class AdaptivePromptManager:
    def __init__(self, student_profile):
        self.profile = student_profile
        
    def get_prompt_style(self):
        """Determine appropriate prompt style based on student profile"""
        if self.profile.skill_level == 'advanced':
            return {
                'verbosity': 'concise',
                'hint_frequency': 'low',
                'example_frequency': 'minimal',
                'question_style': 'challenging'
            }
        elif self.profile.skill_level == 'intermediate':
            return {
                'verbosity': 'moderate',
                'hint_frequency': 'medium',
                'example_frequency': 'when_needed',
                'question_style': 'balanced'
            }
        else:  # beginner
            return {
                'verbosity': 'detailed',
                'hint_frequency': 'high',
                'example_frequency': 'frequent',
                'question_style': 'supportive'
            }
    
    def generate_adaptive_prompt(self, base_prompt):
        """Modify the base prompt based on student's profile"""
        style = self.get_prompt_style()
        
        adaptations = {
            'detailed': "\nPlease provide detailed explanations with examples.",
            'moderate': "\nProvide balanced explanations with occasional examples.",
            'concise': "\nFocus on key concepts with minimal elaboration."
        }
        
        # Add style-specific instructions
        adapted_prompt = base_prompt + adaptations[style['verbosity']]
        
        # Add performance-based modifications
        if self.profile.consecutive_failures > 2:
            adapted_prompt += "\nThe student is currently struggling. Provide more supportive guidance and break down concepts into smaller steps."
        
        return adapted_prompt 